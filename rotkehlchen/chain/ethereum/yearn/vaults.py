from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional

from gevent.lock import Semaphore

from rotkehlchen.accounting.structures import Balance
from rotkehlchen.assets.asset import Asset, EthereumToken
from rotkehlchen.chain.ethereum.structures import YearnVault, YearnVaultEvent
from rotkehlchen.chain.ethereum.utils import token_normalized_value
from rotkehlchen.constants.ethereum import (
    ERC20TOKEN_ABI,
    MAX_BLOCKTIME_CACHE,
    YEARN_ALINK_VAULT,
    YEARN_BCURVE_VAULT,
    YEARN_DAI_VAULT,
    YEARN_SRENCURVE_VAULT,
    YEARN_TUSD_VAULT,
    YEARN_USDC_VAULT,
    YEARN_USDT_VAULT,
    YEARN_WETH_VAULT,
    YEARN_YCRV_VAULT,
    YEARN_YFI_VAULT,
    ZERO_ADDRESS,
)
from rotkehlchen.constants.misc import ZERO
from rotkehlchen.errors import UnknownAsset
from rotkehlchen.fval import FVal
from rotkehlchen.history.price import query_usd_price_zero_if_error
from rotkehlchen.inquirer import SPECIAL_SYMBOLS, Inquirer
from rotkehlchen.premium.premium import Premium
from rotkehlchen.serialization.deserialize import (
    deserialize_blocknumber,
    deserialize_int_from_hex_or_int,
)
from rotkehlchen.typing import ChecksumEthAddress, Price, Timestamp
from rotkehlchen.user_messages import MessagesAggregator
from rotkehlchen.utils.interfaces import EthereumModule
from rotkehlchen.utils.misc import address_to_bytes32, hex_or_bytes_to_int, ts_now

if TYPE_CHECKING:
    from rotkehlchen.chain.ethereum.manager import EthereumManager
    from rotkehlchen.chain.ethereum.zerion import GIVEN_DEFI_BALANCES, DefiProtocolBalances
    from rotkehlchen.db.dbhandler import DBHandler

BLOCKS_PER_YEAR = 2425846


YEARN_VAULTS = {
    'yyDAI+yUSDC+yUSDT+yTUSD': YearnVault(
        name='YCRV Vault',
        contract=YEARN_YCRV_VAULT,
        underlying_token=EthereumToken('yDAI+yUSDC+yUSDT+yTUSD'),
        token=EthereumToken('yyDAI+yUSDC+yUSDT+yTUSD'),
    ),
    'yDAI': YearnVault(
        name='YDAI Vault',
        contract=YEARN_DAI_VAULT,
        underlying_token=EthereumToken('DAI'),
        token=EthereumToken('yDAI'),
    ),
    'yWETH': YearnVault(
        name='YWETH Vault',
        contract=YEARN_WETH_VAULT,
        underlying_token=EthereumToken('WETH'),
        token=EthereumToken('yWETH'),
    ),
    'yYFI': YearnVault(
        name='YYFI Vault',
        contract=YEARN_YFI_VAULT,
        underlying_token=EthereumToken('YFI'),
        token=EthereumToken('yYFI'),
    ),
    'yaLINK': YearnVault(
        name='YALINK Vault',
        contract=YEARN_ALINK_VAULT,
        underlying_token=EthereumToken('aLINK'),
        token=EthereumToken('yaLINK'),
    ),
    'yUSDT': YearnVault(
        name='YUSDT Vault',
        contract=YEARN_USDT_VAULT,
        underlying_token=EthereumToken('USDT'),
        token=EthereumToken('yUSDT'),
    ),
    'yUSDC': YearnVault(
        name='YUSDC Vault',
        contract=YEARN_USDC_VAULT,
        underlying_token=EthereumToken('USDC'),
        token=EthereumToken('yUSDC'),
    ),
    'yTUSD': YearnVault(
        name='YTUSD Vault',
        contract=YEARN_TUSD_VAULT,
        underlying_token=EthereumToken('TUSD'),
        token=EthereumToken('yTUSD'),
    ),
    'yyDAI+yUSDC+yUSDT+yBUSD': YearnVault(
        name='YBCURVE Vault',
        contract=YEARN_BCURVE_VAULT,
        underlying_token=EthereumToken('yDAI+yUSDC+yUSDT+yBUSD'),
        token=EthereumToken('yyDAI+yUSDC+yUSDT+yBUSD'),
    ),
    'ycrvRenWSBTC': YearnVault(
        name='YSRENCURVE Vault',
        contract=YEARN_SRENCURVE_VAULT,
        underlying_token=EthereumToken('crvRenWSBTC'),
        token=EthereumToken('ycrvRenWSBTC'),
    ),
}


class YearnVaultHistory(NamedTuple):
    events: List[YearnVaultEvent]
    profit_loss: Balance


class YearnVaultBalance(NamedTuple):
    underlying_token: Asset
    vault_token: Asset
    underlying_value: Balance
    vault_value: Balance
    roi: FVal

    def serialize(self) -> Dict[str, Any]:
        result = self._asdict()  # pylint: disable=no-member
        result['roi'] = self.roi.to_percentage(precision=2)
        return result


def get_usd_price_zero_if_error(
        asset: Asset,
        time: Timestamp,
        location: str,
        msg_aggregator: MessagesAggregator,
) -> Price:
    """A special version of query_usd_price_zero_if_error using current price instead
    of historical token price for some assets.

    Since these assets are not supported by our price oracles we derive current
    price from the chain but without an archive node can't query old prices.

    TODO: MAke an issue about this
    This can be solved when we have an archive node.
    """
    if asset.identifier in SPECIAL_SYMBOLS:
        return Inquirer().find_usd_price(asset)

    return query_usd_price_zero_if_error(
        asset=asset,
        time=time,
        location=location,
        msg_aggregator=msg_aggregator,
    )


class YearnVaults(EthereumModule):

    def __init__(
            self,
            ethereum_manager: 'EthereumManager',
            database: 'DBHandler',
            premium: Optional[Premium],
            msg_aggregator: MessagesAggregator,
    ) -> None:
        self.ethereum = ethereum_manager
        self.database = database
        self.msg_aggregator = msg_aggregator
        self.premium = premium
        self.history_lock = Semaphore()

    def _calculate_vault_roi(self, vault: YearnVault) -> FVal:
        """
        getPricePerFullShare A @ block X
        getPricePerFullShare B @ block Y

        (A-B / X-Y) * blocksPerYear (2425846)

        So the numbers you see displayed on http://yearn.finance/vaults
        are ROI since launch of contract. All vaults start with pricePerFullShare = 1e18
        """
        now_block_number = self.ethereum.get_latest_block_number()
        price_per_full_share = self.ethereum.call_contract(
            contract_address=vault.contract.address,
            abi=YEARN_DAI_VAULT.abi,  # Any vault ABI will do
            method_name='getPricePerFullShare',
        )
        nominator = price_per_full_share - (10**18)
        denonimator = now_block_number - vault.contract.deployed_block
        return FVal(nominator) / FVal(denonimator) * BLOCKS_PER_YEAR / 10**18

    def _get_single_addr_balance(
            self,
            defi_balances: List['DefiProtocolBalances'],
            roi_cache: Dict[str, FVal],
    ) -> Dict[str, YearnVaultBalance]:
        result = {}
        for balance in defi_balances:
            if balance.protocol.name == 'yearn.finance • Vaults':
                underlying_symbol = balance.underlying_balances[0].token_symbol
                vault_symbol = balance.base_balance.token_symbol
                vault = YEARN_VAULTS.get(vault_symbol, None)
                if vault is None:
                    self.msg_aggregator.add_warning(
                        f'Found balance for unsupported yearn vault {vault_symbol}',
                    )
                    continue

                try:
                    underlying_asset = Asset(underlying_symbol)
                    vault_asset = Asset(vault_symbol)
                except UnknownAsset as e:
                    self.msg_aggregator.add_warning(
                        f'Found unknown asset {e.asset_name} for yearn vault entry',
                    )
                    continue

                roi = roi_cache.get(underlying_symbol, None)
                if roi is None:
                    roi = self._calculate_vault_roi(vault)
                    roi_cache[underlying_symbol] = roi

                result[vault.name] = YearnVaultBalance(
                    underlying_token=underlying_asset,
                    vault_token=vault_asset,
                    underlying_value=balance.underlying_balances[0].balance,
                    vault_value=balance.base_balance.balance,
                    roi=roi,
                )

        return result

    def get_balances(
            self,
            given_defi_balances: 'GIVEN_DEFI_BALANCES',
    ) -> Dict[ChecksumEthAddress, Dict[str, YearnVaultBalance]]:
        if isinstance(given_defi_balances, dict):
            defi_balances = given_defi_balances
        else:
            defi_balances = given_defi_balances()

        roi_cache: Dict[str, FVal] = {}
        result = {}
        for address, balances in defi_balances.items():
            vault_balances = self._get_single_addr_balance(balances, roi_cache)
            if len(vault_balances) != 0:
                result[address] = vault_balances

        return result

    def _get_vault_deposit_events(
            self,
            vault: YearnVault,
            address: ChecksumEthAddress,
            from_block: int,
            to_block: int,
    ) -> List[YearnVaultEvent]:
        """Get all deposit events of the underlying token to the vault"""
        events: List[YearnVaultEvent] = []
        argument_filters = {'from': address, 'to': vault.contract.address}
        deposit_events = self.ethereum.get_logs(
            contract_address=vault.underlying_token.ethereum_address,
            abi=ERC20TOKEN_ABI,
            event_name='Transfer',
            argument_filters=argument_filters,
            from_block=from_block,
            to_block=to_block,
        )
        for deposit_event in deposit_events:
            timestamp = self.ethereum.get_event_timestamp(deposit_event)
            deposit_amount = token_normalized_value(
                hex_or_bytes_to_int(deposit_event['data']),
                vault.underlying_token.decimals,
            )
            tx_hash = deposit_event['transactionHash']
            tx_receipt = self.ethereum.get_transaction_receipt(tx_hash)
            deposit_index = deserialize_int_from_hex_or_int(
                deposit_event['logIndex'],
                'yearn deposit log index',
            )
            mint_amount = None
            for log in tx_receipt['logs']:
                found_event = (
                    log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef' and  # noqa: E501
                    log['topics'][1] == address_to_bytes32(ZERO_ADDRESS) and
                    log['topics'][2] == address_to_bytes32(address)
                )
                if found_event:
                    # found the mint log
                    mint_amount = token_normalized_value(
                        hex_or_bytes_to_int(log['data']),
                        vault.token.decimals,
                    )

            if mint_amount is None:
                self.msg_aggregator.add_error(
                    f'Ignoring yearn deposit event with tx_hash {tx_hash} and log index '
                    f'{deposit_index} due to inability to find corresponding mint event',
                )
                continue

            deposit_usd_price = get_usd_price_zero_if_error(
                asset=vault.underlying_token,
                time=timestamp,
                location='yearn vault deposit',
                msg_aggregator=self.msg_aggregator,
            )
            mint_usd_price = get_usd_price_zero_if_error(
                asset=vault.token,
                time=timestamp,
                location='yearn vault deposit',
                msg_aggregator=self.msg_aggregator,
            )
            events.append(YearnVaultEvent(
                event_type='deposit',
                block_number=deserialize_blocknumber(deposit_event['blockNumber']),
                timestamp=timestamp,
                from_asset=vault.underlying_token,
                from_value=Balance(
                    amount=deposit_amount,
                    usd_value=deposit_amount * deposit_usd_price,
                ),
                to_asset=vault.token,
                to_value=Balance(
                    amount=mint_amount,
                    usd_value=mint_amount * mint_usd_price,
                ),
                realized_pnl=None,
                tx_hash=tx_hash,
                log_index=deposit_index,
            ))

        return events

    def _get_vault_withdraw_events(
            self,
            vault: YearnVault,
            address: ChecksumEthAddress,
            from_block: int,
            to_block: int,
    ) -> List[YearnVaultEvent]:
        """Get all withdraw events of the underlying token to the vault"""
        events: List[YearnVaultEvent] = []
        argument_filters = {'from': vault.contract.address, 'to': address}
        withdraw_events = self.ethereum.get_logs(
            contract_address=vault.underlying_token.ethereum_address,
            abi=ERC20TOKEN_ABI,
            event_name='Transfer',
            argument_filters=argument_filters,
            from_block=from_block,
            to_block=to_block,
        )
        for withdraw_event in withdraw_events:
            timestamp = self.ethereum.get_event_timestamp(withdraw_event)
            withdraw_amount = token_normalized_value(
                hex_or_bytes_to_int(withdraw_event['data']),
                vault.token.decimals,
            )
            tx_hash = withdraw_event['transactionHash']
            tx_receipt = self.ethereum.get_transaction_receipt(tx_hash)
            withdraw_index = deserialize_int_from_hex_or_int(
                withdraw_event['logIndex'],
                'yearn withdraw log index',
            )
            burn_amount = None
            for log in tx_receipt['logs']:
                found_event = (
                    log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef' and  # noqa: E501
                    log['topics'][1] == address_to_bytes32(address) and
                    log['topics'][2] == address_to_bytes32(ZERO_ADDRESS)
                )
                if found_event:
                    # found the burn log
                    burn_amount = token_normalized_value(
                        hex_or_bytes_to_int(log['data']),
                        vault.token.decimals,
                    )

            if burn_amount is None:
                self.msg_aggregator.add_error(
                    f'Ignoring yearn withdraw event with tx_hash {tx_hash} and log index '
                    f'{withdraw_index} due to inability to find corresponding burn event',
                )
                continue

            withdraw_usd_price = get_usd_price_zero_if_error(
                asset=vault.underlying_token,
                time=timestamp,
                location='yearn vault withdraw',
                msg_aggregator=self.msg_aggregator,
            )
            burn_usd_price = get_usd_price_zero_if_error(
                asset=vault.token,
                time=timestamp,
                location='yearn vault withdraw',
                msg_aggregator=self.msg_aggregator,
            )
            events.append(YearnVaultEvent(
                event_type='withdraw',
                block_number=deserialize_blocknumber(withdraw_event['blockNumber']),
                timestamp=timestamp,
                from_asset=vault.token,
                from_value=Balance(
                    amount=burn_amount,
                    usd_value=burn_amount * burn_usd_price,
                ),
                to_asset=vault.underlying_token,
                to_value=Balance(
                    amount=withdraw_amount,
                    usd_value=withdraw_amount * withdraw_usd_price,
                ),
                realized_pnl=None,
                tx_hash=tx_hash,
                log_index=withdraw_index,
            ))

        return events

    def _process_vault_events(self, events: List[YearnVaultEvent]) -> Balance:
        """Process the events for a single vault and returns total profit/loss after all events"""
        total = Balance()
        profit_so_far = Balance()
        for event in events:
            if event.event_type == 'deposit':
                total -= event.from_value
            else:  # withdraws
                profit_amount = total.amount + event.to_value.amount - profit_so_far.amount
                profit: Optional[Balance]
                if profit_amount >= 0:
                    usd_price = get_usd_price_zero_if_error(
                        asset=event.to_asset,
                        time=event.timestamp,
                        location='yearn vault event processing',
                        msg_aggregator=self.msg_aggregator,
                    )
                    profit = Balance(profit_amount, profit_amount * usd_price)
                    profit_so_far += profit
                else:
                    profit = None

                event.realized_pnl = profit
                total += event.to_value

        return total

    def get_vault_history(
            self,
            defi_balances: List['DefiProtocolBalances'],
            vault: YearnVault,
            address: ChecksumEthAddress,
            from_block: int,
            to_block: int,
    ) -> Optional[YearnVaultHistory]:
        from_block = max(from_block, vault.contract.deployed_block)
        last_query = self.database.get_used_query_range(f'yearn_vaults_events_{address}')
        skip_query = last_query and to_block - last_query[1] < MAX_BLOCKTIME_CACHE

        events = self.database.get_yearn_vaults_events(address=address, vault=vault)
        if not skip_query:
            new_events = self._get_vault_deposit_events(vault, address, from_block, to_block)
            if len(events) == 0 and len(new_events) == 0:
                return None

            new_events.extend(
                self._get_vault_withdraw_events(vault, address, from_block, to_block),
            )
            # Now update the DB with the new events
            self.database.add_yearn_vaults_events(address, new_events)

        events.sort(key=lambda x: x.timestamp)
        total_pnl = self._process_vault_events(events)

        current_balance = None
        for balance in defi_balances:
            found_balance = (
                balance.protocol.name == 'yearn.finance • Vaults' and
                balance.base_balance.token_symbol == vault.token.symbol
            )
            if found_balance:
                current_balance = balance.underlying_balances[0].balance
                total_pnl += current_balance
                break

        # Due to the way we calculate usd prices for vaults we need to get the current
        # usd price of the actual pnl amount at this point
        if total_pnl.amount != ZERO:
            usd_price = get_usd_price_zero_if_error(
                asset=vault.underlying_token,
                time=ts_now(),
                location='yearn vault history',
                msg_aggregator=self.msg_aggregator,
            )
            total_pnl.usd_value = usd_price * total_pnl.amount
        return YearnVaultHistory(events=events, profit_loss=total_pnl)

    def get_history(
            self,
            given_defi_balances: 'GIVEN_DEFI_BALANCES',
            addresses: List[ChecksumEthAddress],
            reset_db_data: bool,
            from_timestamp: Timestamp,  # pylint: disable=unused-argument
            to_timestamp: Timestamp,  # pylint: disable=unused-argument
    ) -> Dict[ChecksumEthAddress, Dict[str, YearnVaultHistory]]:
        with self.history_lock:

            if reset_db_data is True:
                self.database.delete_yearn_vaults_data()

            if isinstance(given_defi_balances, dict):
                defi_balances = given_defi_balances
            else:
                defi_balances = given_defi_balances()

            from_block = self.ethereum.etherscan.get_blocknumber_by_time(from_timestamp)
            to_block = self.ethereum.etherscan.get_blocknumber_by_time(to_timestamp)
            history: Dict[ChecksumEthAddress, Dict[str, YearnVaultHistory]] = {}
            for address in addresses:
                history[address] = {}
                last_query = self.database.get_used_query_range(f'yearn_vaults_events_{address}')
                if last_query and to_block - last_query[1] < MAX_BLOCKTIME_CACHE:
                    continue  # save time by not querying events if last query is recent

                for _, vault in YEARN_VAULTS.items():
                    vault_history = self.get_vault_history(
                        defi_balances=defi_balances[address],
                        vault=vault,
                        address=address,
                        from_block=last_query[1] + 1 if last_query is not None else from_block,
                        to_block=to_block,
                    )
                    if vault_history:
                        history[address][vault.name] = vault_history

                if len(history[address]) == 0:
                    del history[address]

        return history

    # -- Methods following the EthereumModule interface -- #
    def on_startup(self) -> None:
        pass

    def on_account_addition(self, address: ChecksumEthAddress) -> None:
        pass

    def on_account_removal(self, address: ChecksumEthAddress) -> None:
        pass

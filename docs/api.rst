Rotki API
##################################################
.. toctree::
  :maxdepth: 2


Introduction
*************

When the Rotki backend runs it exposes an HTTP Rest API that is accessed by either the electron front-end or a web browser. The endpoints accept and return JSON encoded objects. All queries have the following prefix: ``/api/<version>/`` where ``version`` is the current version. The current version at the moment is ``1``.


Response Format
*****************

All endpoints have their response wrapped in the following JSON object

::

    {
        "result": 42,
	"message": ""
    }


In the case of a succesful response the ``"result"`` attribute is populated and is not ``null`` and the ``"message"`` is empty.

::

    {
        "result": null,
	"message": "An error happened"
    }

In the case of a failed response the ``"result"`` attribute is going to be ``null`` and the ``"message"`` attribute will optionally contain information about the error.

Endpoints
***********

In this section we will see the information about the individual endpoints of the API and detailed explanation of how each one can be used to interact with Rotki.

Logging out of the current user account
=======================================

.. http:get:: /api/(version)/logout

   With this endpoint you can logout from your currently logged in account. All user related data will be saved in the database, memory cleared and encrypted database connection closed.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      GET /api/1/logout HTTP/1.1
      Host: localhost:5042

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": true,
	  "message": ""
      }


Getting or modifying settings
==============================

.. http:get:: /api/(version)/settings

   By doing a GET on the settings endpoint you can get all the user settings for
   the currently logged in account

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      GET /api/1/settings HTTP/1.1
      Host: localhost:5042
      Content-Type: application/json

      {}

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {
	      "version": "6",
	      "last_write_ts": 1571552172,
	      "premium_should_sync": true,
	      "include_crypto2crypto": true,
	      "anonymized_logs": true,
	      "last_data_upload_ts": 1571552172,
	      "ui_floating_precision": 2,
	      "taxfree_after_period": 31536000,
	      "balance_save_frequency": 24,
	      "include_gas_costs": true,
	      "historical_data_start": "01/08/2015",
	      "eth_rpc_endpoint": "http://localhost:8545",
	      "main_currency": "USD",
	      "date_display_format": "%d/%m/%Y %H:%M:%S %Z",
	      "last_balance_save": 1571552172
	  },
	  "message": ""
      }

   :statuscode 200: Querying of settings was succesful
   :statuscode 500: Internal Rotki error

   :reqjson int version: The database version
   :reqjson int last_write_ts: The unix timestamp at which an entry was last written in the database
   :reqjson bool premium_should_sync: A boolean denoting whether premium users database should be synced from/to the server
   :reqjson bool include_crypto2crypto: A boolean denoting whether crypto to crypto trades should be counted.
   :reqjson bool anonymized_logs: A boolean denoting whether sensitive logs should be anonymized.
   :reqjson int last_data_upload_ts: The unix timestamp at which the last data upload to the server happened.
   :reqjson int ui_floating_precision: The number of decimals points to be shown for floating point numbers in the UI
   :reqjson int taxfree_after_period: The number of seconds after which holding a crypto in FIFO order is considered no longer taxable. The default is 1 year, as per current german tax rules. Can also be 0 which means there is no taxfree period.
   :reqjson int balance_save_frequency: The number of hours after which user balances should be saved in the DB again. This is useful for the statistics kept in the DB for each user. Default is 24 hours.
   :reqjson bool include_gas_costs: A boolean denoting whether gas costs should be counted as loss in profit/loss calculation.
   :reqjson string historical_data_start: A date in the DAY/MONTH/YEAR format at which we consider historical data to have started.
   :reqjson string eth_rpc_endpoint: A URL denoting the rpc endpoint for the ethereum node to use when contacting the ethereum blockchain. If it can not be reached or if it is invalid etherscan is used instead.
   :reqjson string main_currency: The FIAT currency to use for all profit/loss calculation. USD by default.
   :reqjson string date_display_format: The format in which to display dates in the UI. Default is ``"%d/%m/%Y %H:%M:%S %Z"``.
   :reqjson int last_balance_save: The timestamp at which the balances were last saved in the database.

.. http:put:: /api/(version)/settings

   By doing a PUT on the settings endpoint you can set/modify any settings you need

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      PUT /api/1/settings HTTP/1.1
      Host: localhost:5042
      Content-Type: application/json

      {
          "ui_floating_precision": 4,
          "include_gas_costs": false
      }

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {
	      "version": "6",
	      "last_write_ts": 1571552172,
	      "premium_should_sync": true,
	      "include_crypto2crypto": true,
	      "anonymized_logs": true,
	      "last_data_upload_ts": 1571552172,
	      "ui_floating_precision": 4,
	      "taxfree_after_period": 31536000,
	      "balance_save_frequency": 24,
	      "include_gas_costs": false,
	      "historical_data_start": "01/08/2015",
	      "eth_rpc_endpoint": "http://localhost:8545",
	      "main_currency": "USD",
	      "date_display_format": "%d/%m/%Y %H:%M:%S %Z",
	      "last_balance_save": 1571552172
	  },
	  "message": ""
      }

   :statuscode 200: Modifying settings was succesful
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 409: Invalid input, e.g. not the correct type for a setting
   :statuscode 500: Internal Rotki error

Query the result of an ongoing backend task
===========================================

.. http:get:: /api/(version)/task_result

   By querying this endpoint with a particular task identifier you can get the result of the task if it has finished and the result has not yet been queried. If the result is still in progress or if the result is not found appropriate responses are returned.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      GET /api/1/logout HTTP/1.1
      Host: localhost:5042

      {"task_id": 42}

   **Example Completed Response**:

   The following is an example response of an async query to exchange balances.

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {
	      "status": "completed",
	      "outcome": {
	          "per_account": {"BTC": {
	              "1Ec9S8KSw4UXXhqkoG3ZD31yjtModULKGg": {
	          	      "amount": "10",
	          	      "usd_value": "70500.15"
	          	  }
	          }},
	          "totals": {"BTC": {"amount": "10", "usd_value": "70500.15"}}
	      }
	  },
	  "message": ""
      }

   **Example Pending Response**:

   The following is an example response of an async query that is still in progress.

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {
	      "status": "pending",
	      "outcome": null
	  },
	  "message": ""
      }

   **Example Not Found Response**:

   The following is an example response of an async query that is still in progress.

   .. sourcecode:: http

      HTTP/1.1 404 OK
      Content-Type: application/json

      {
          "result": {
	      "status": "not found",
	      "outcome": null
	  },
	  "message": "No task with the task id 42 found"
      }

   :statuscode 200: The task's outcome is succesfully returned or pending
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 404: There is no task with the given task id
   :statuscode 500: Internal Rotki error

Query the current fiat currencies exchange rate
===============================================

.. http:get:: /api/(version)/fiat_exchange_rates

   Querying this endpoint with a list of strings representing FIAT currencies will return a dictionary of their current exchange rates compared to USD.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      GET /api/1/logout HTTP/1.1
      Host: localhost:5042

      ["EUR", "CNY", "GBP"]

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {"EUR": "0.8973438622", "CNY": "7.0837221823", "GBP": "0.7756191673"},
	  "message": ""
      }

   :statuscode 200: The exchange rates have been sucesfully returned
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 500: Internal Rotki error

Setup or remove an exchange
============================

.. http:put:: /api/(version)/exchange

   Doing a PUT on this endpoint with an exchange's name, api key and secret will setup the exchange for the current user.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      PUT /api/1/exchange HTTP/1.1
      Host: localhost:5042

      {"name": "kraken", "api_key": "ddddd", "api_secret": "ffffff"}

   :reqjson string name: The name of the exchange to setup
   :reqjson string api_key: The api key with which to setup the exchange
   :reqjson string api_secret: The api secret with which to setup the exchange

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": true
	  "message": ""
      }

   :statuscode 200: The exchange has been sucesfully setup
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 409: The exchange has already been registered or some other error
   :statuscode 500: Internal Rotki error

.. http:delete:: /api/(version)/exchange

   Doing a DELETE on this endpoint for a particular exchange name will delete the exchange from the database for the current user.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      DELETE /api/1/exchange HTTP/1.1
      Host: localhost:5042

      {"name": "kraken"}

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": true
	  "message": ""
      }

   :statuscode 200: The exchange has been sucesfully delete
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 409: The exchange is not registered or some other error
   :statuscode 500: Internal Rotki error

Dealing with external trades
============================

.. http:get:: /api/(version)/trades

   Doing a GET on this endpoint will return all trades. They can be further

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      GET /api/1/trades HTTP/1.1
      Host: localhost:5042

      {"from_timestamp": 1451606400, "to_timestamp": 1571663098, "location": "external"}

   :reqjson int from_timestamp: The timestamp from which to query. Can be missing inwhich case we query from 0.
   :reqjson int to_timestamp: The timestamp until which to query. Can be missing in which case we query until now.
   :reqjson string location: Optionally filter trades by location. A valid location name has to be provided. If missing location filtering does not happen.

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": [{
	      "trade_id": "dsadfasdsad",
	      "timestamp": 1491606401,
	      "location": "external",
	      "pair": "BTC_EUR",
	      "trade_type": "buy",
	      "amount": "0.5541",
	      "rate": "8422.1",
	      "fee": "0.55",
	      "fee_currency": "USD",
	      "link": "Optional unique trade identifier"
	      "notes": "Optional notes"
	  }]
	  "message": ""
      }

   :statuscode 200: Trades are succesfully returned
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 500: Internal Rotki error

.. http:put:: /api/(version)/trades

   Doing a PUT on this endpoint adds a new trade to Rotki.

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      PUT /api/1/trades HTTP/1.1
      Host: localhost:5042

      {
          "timestamp": 1491606401,
          "location": "external",
          "pair": "BTC_EUR",
          "trade_type": "buy",
          "amount": "0.5541",
          "rate": "8422.1",
          "fee": "0.55",
          "fee_currency": "USD",
          "link": "Optional unique trade identifier"
          "notes": "Optional notes"
      }

   :reqjson int timestamp: The timestamp at which the trade occured
   :reqjson string location: A valid location at which the trade happened
   :reqjson string pair: The pair for the trade. e.g. ``"BTC_EUR"``
   :reqjson string trade_type: The type of the trade. e.g. ``"buy"`` or ``"sell"``
   :reqjson string amount: The amount that was bought or sold
   :reqjson string rate: The rate at which 1 unit of ``base_asset`` was exchanges for 1 unit of ``quote_asset``
   :reqjson string fee: The fee that was paid, if anything, for this trade
   :reqjson string fee_currency: The currency in which ``fee`` is denominated in
   :reqjson string link: Optional unique trade identifier or link to the trade. Can be an empty string
   :reqjson string notes: Optional notes about the trade. Can be an empty string

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": [{
	      "trade_id": "dsadfasdsad",
	      "timestamp": 1491606401,
	      "location": "external",
	      "pair": "BTC_EUR",
	      "trade_type": "buy",
	      "amount": "0.5541",
	      "rate": "8422.1",
	      "fee": "0.55",
	      "fee_currency": "USD",
	      "link": "Optional unique trade identifier"
	      "notes": "Optional notes"
	  }]
	  "message": ""
      }

   :statuscode 200: Trades was succesfully added.
   :statuscode 400: Provided JSON is in some way malformed
   :statuscode 500: Internal Rotki error

.. http:patch:: /api/(version)/trades

   Doing a PATCH on this endpoint edits an existing trade in Rotki using the ``trade_identifier``

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      PATCH /api/1/trades HTTP/1.1
      Host: localhost:5042

      {
          "trade_id" : "dsadfasdsad",
          "timestamp": 1491606401,
          "location": "external",
          "pair": "BTC_EUR",
          "trade_type": "buy",
          "amount": "1.5541",
          "rate": "8422.1",
          "fee": "0.55",
          "fee_currency": "USD",
          "link": "Optional unique trade identifier"
          "notes": "Optional notes"
      }

   :reqjson string trade_id: The ``trade_id`` of the trade to edit
   :reqjson int timestamp: The new timestamp
   :reqjson string location: The new location
   :reqjson string pair: The new pair
   :reqjson string trade_type: The new trade type
   :reqjson string rate: The new trade rate
   :reqjson string fee: The new fee
   :reqjson string fee_currency: The new fee currency
   :reqjson string link: The new link attribute
   :reqjson string notes: The new notes attribute

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": {
	      "trade_id": "sdfhdjskfha",
	      "timestamp": 1491606401,
	      "location": "external",
	      "pair": "BTC_EUR",
	      "trade_type": "buy",
	      "amount": "1.5541",
	      "rate": "8422.1",
	      "fee": "0.55",
	      "fee_currency": "USD",
	      "link": "Optional unique trade identifier"
	      "notes": "Optional notes"
	  }
	  "message": ""
      }

   :statuscode 200: Trades was succesfully edited.
   :statuscode 400: Provided JSON is in some way malformed.
   :statuscode 409: The given trade identifier to edit does not exist.
   :statuscode 500: Internal Rotki error.

.. http:delete:: /api/(version)/trades

   Doing a DELETE on this endpoint deletes an existing trade in Rotki using the ``trade_identifier``

   **Example Request**:

   .. http:example:: curl wget httpie python-requests

      DELETE /api/1/trades HTTP/1.1
      Host: localhost:5042

      { "trade_id" : "dsadfasdsad"}

   :reqjson string trade_id: The ``trade_id`` of the trade to delete.

   **Example Response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Content-Type: application/json

      {
          "result": true,
	  "message": ""
      }

   :statuscode 200: Trades was succesfully deleted.
   :statuscode 400: Provided JSON is in some way malformed.
   :statuscode 409: The given trade identifier to delete does not exist.
   :statuscode 500: Internal Rotki error.
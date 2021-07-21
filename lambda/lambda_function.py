#### AUTHOR  - RANJITH KUMAR MADHAVAN       ####
#### WEBSITE - https://programmerview.com/  ####

import logging
import os
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.ui import SimpleCard,AskForPermissionsConsentCard
from datetime import datetime,date,timedelta
from ask_sdk_model.interfaces.connections.send_request_directive import SendRequestDirective
from ask_sdk_model.intent import Intent
from ask_sdk_model.dialog.elicit_slot_directive import ElicitSlotDirective
from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_model import Response
from dateutil.parser import parse
from ask_sdk_dynamodb.adapter import DynamoDbAdapter
import boto3
from ask_sdk_model.interfaces.amazonpay.request.setup_amazon_pay_request import SetupAmazonPayRequest
from decimal import Decimal
import random
import string
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
sellerId = os.environ['SELLER_ID']
sandboxCustomerEmailId = os.environ['SANDBOX_CUSTOMER_EMAIL_ID']
amazonpay_permission = ["payments:autopay_consent"]

# Defining the database region, table name and dynamodb persistence adapter
ddb_table_name = "alexa-amazon-pay"
ddb_resource = boto3.resource('dynamodb')
dynamodb_adapter = DynamoDbAdapter(table_name=ddb_table_name, create_table=True, dynamodb_resource=ddb_resource)

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        logger.info("inside LaunchRequestHandler()")
        speak_output = "Welcome to amazon pay payment. You can say pay my bill to pay"
        return handler_input.response_builder.speak(speak_output).ask(speak_output).response

class PayIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("PayIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("inside PayIntentHandler()")
        permissions = handler_input.request_envelope.context.system.user.permissions
        session_attr = handler_input.attributes_manager.session_attributes
        if "DENIED" in str(permissions.scopes["payments:autopay_consent"].status):
            speak_output = "Please provide the permissions to your Amazon Pay account. Open the Alexa app and navigate to the Activity page."
            logger.info(f"Alexa message - {speak_output}")
            logger.info(f"session_attributes - {session_attr}")
            return (
                handler_input.response_builder
                    .set_card(AskForPermissionsConsentCard(permissions=amazonpay_permission))
                    .speak(speak_output)
                    .response
            )
        token = generateRandomNString(12)
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        persistent_attributes["amount"] = Decimal(150)
        # Write user's name to the DB.
        handler_input.attributes_manager.save_persistent_attributes()
        payload = {
            "@type": "SetupAmazonPayRequest",
            "@version": "2",
            "sellerId": sellerId,
            "countryOfEstablishment": "US",
            "ledgerCurrency": "USD",
            "checkoutLanguage": "en-US",
            "billingAgreementAttributes": {
                "@type": "BillingAgreementAttributes",
                "@version": "2",
                # "billingAgreementType": "CustomerInitiatedTransaction",#EU and UK merchants only
                "sellerNote": "Billing Agreement Seller Note",
                "sellerBillingAgreementAttributes": {
                    "@type": "SellerBillingAgreementAttributes",
                    "@version": "2",
                    "sellerBillingAgreementId": generateRandomNString(6),
                    "storeName": "YOUR STORE NAME",
                    "customInformation": "YOUR CUSTOM INFORMATION"
                }
            },
            "needAmazonShippingAddress": False,
            "sandboxCustomerEmailId" : sandboxCustomerEmailId, #uncomment it for production
            "sandboxMode" : True #change it to False for True
        }
        return handler_input.response_builder.add_directive(SendRequestDirective("Setup",payload,token)).set_should_end_session(True).response  
        
class SetupIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return handler_input.request_envelope.request.object_type == "Connections.Response" and handler_input.request_envelope.request.name == "Setup"

    def handle(self, handler_input):
        logger.info("inside SetupIntentHandler()")
        connectionResponsePayload = handler_input.request_envelope.request.payload
        connectionResponseStatusCode = handler_input.request_envelope.request.status.code
        if int(connectionResponseStatusCode) != 200:
            speak_output = f"Please try again. {connectionResponseStatusCode}"
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        billingAgreementID = connectionResponsePayload["billingAgreementDetails"]["billingAgreementId"];
        billingAgreementStatus = connectionResponsePayload["billingAgreementDetails"]["billingAgreementStatus"];
        # If billingAgreementStatus is valid, Charge the payment method
        if billingAgreementStatus == "OPEN":
            persistent_attributes["billingAgreementId"] = billingAgreementID
            if 'amount' in persistent_attributes:
                amount = Decimal(persistent_attributes["amount"])
            # Write user's name to the DB.
            handler_input.attributes_manager.save_persistent_attributes()
            payload = {
                    "@type": "ChargeAmazonPayRequest",
                    "@version": "2",
                    "sellerId": sellerId,
                    "billingAgreementId": billingAgreementID,
                    "paymentAction": "AuthorizeAndCapture",
                    "authorizeAttributes": {
                        "@type": "AuthorizeAttributes",
                        "@version": "2",
                        "authorizationReferenceId": generateRandomNString(16),
                        "authorizationAmount": {
                            "@type": "Price",
                            "@version": "2",
                            "amount": str(amount),
                            "currencyCode": "USD"
                        },
                        "transactionTimeout": 0,
                        "sellerAuthorizationNote": "YOUR SELLER AUTHORIZATION NOTE"
                    },
                    "sellerOrderAttributes": {
                        "@type": "SellerOrderAttributes",
                        "@version": "2",
                        "sellerOrderId": generateRandomNString(6),
                        "storeName": "YOUR STORE NAME",
                        "customInformation": "YOUR CUSTOM INFORMATION",
                        "sellerNote": "YOUR SELLER NOTE"
                    }
            }
            token = generateRandomNString(12)
            return handler_input.response_builder.add_directive(SendRequestDirective("Charge",payload,token)).set_should_end_session(True).response
        else:
            speak_output = f'There was a problem when processing you request. Reach out to the support team to resolve this issue.'
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
            
class ChargeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return handler_input.request_envelope.request.object_type == "Connections.Response" and handler_input.request_envelope.request.name == "Charge"

    def handle(self, handler_input):
        logger.info("inside ChargeIntentHandler()")
        connectionResponsePayload = handler_input.request_envelope.request.payload
        connectionResponseStatusCode = handler_input.request_envelope.request.status.code
        if int(connectionResponseStatusCode) != 200:
            speak_output = "Sorry there was a problem when processing your request. Your money is not debited. Please contact our support team!!"
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
        session_attr = handler_input.attributes_manager.session_attributes
        authorizationStatusState = connectionResponsePayload["authorizationDetails"]["authorizationStatus"]["state"]
        if authorizationStatusState == "Declined":
            authorizationStatusReasonCode = connectionResponsePayload["authorizationDetails"]["reasonCode"]
            speak_output = f"Your order was not placed. reason code is {authorizationStatusReasonCode}"
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
        else:
            speak_output = "Your order is placed successfully"
            confirmationIntentResponse = "Your order is placed successfully"
            card_title = 'Order Confirmation Details'
            # Delete all attributes from the DB
            handler_input.attributes_manager.delete_persistent_attributes()
            return (
                handler_input.response_builder
                    .set_card(SimpleCard(card_title, confirmationIntentResponse))
                    .speak(speak_output)
                    .set_should_end_session(True)
                    .response
            )
            
class RefundOrderIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("RefundOrderIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("inside RefundOrderIntentHandler()")
        speak_output = "To request a refund, email or call us. I sent contact information to your Alexa app."
        card_title = "Refund Order Details"
        storePhoneNumber = ""
        storeEmail = ""
        card_text = 'Not completely happy with your order? We are here to help.\n To request a refund, contact us at '+ storePhoneNumber +' or email '+ storeEmail +'.'
        return handler_input.response_builder.set_card(SimpleCard(card_title, card_text)).speak(speak_output).set_should_end_session(True).response
        
class CancelOrderIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("CancelOrderIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("inside CancelOrderIntentHandler()")
        speak_output = "To request a cancellation, email or call us. I sent contact information to your Alexa app."
        card_title = "Cancel Order Details"
        storePhoneNumber = ""
        storeEmail = ""
        card_text = 'Want to change or cancel your order? We are here to help.\n To request a refund, contact us at '+ storePhoneNumber +' or email '+ storeEmail +'.'
        return handler_input.response_builder.set_card(SimpleCard(card_title, card_text)).speak(speak_output).set_should_end_session(True).response
            
class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("inside HelpIntentHandler()")
        # type: (HandlerInput) -> Response
        speak_output = "You can say, pay my bill to pay or exit to quit"
        session_attr = handler_input.attributes_manager.session_attributes
        logger.info(f"Alexa message - {speak_output}")
        logger.info(f"session_attributes - {session_attr}")
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        logger.info("inside CancelOrStopIntentHandler()")
        session_attr = handler_input.attributes_manager.session_attributes
        speak_output = "Goodbye!"
        logger.info(f"Alexa message - {speak_output}")
        logger.info(f"session_attributes - {session_attr}")
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        logger.info("inside SessionEndedRequestHandler()")
        session_attr = handler_input.attributes_manager.session_attributes
        logger.info(f"session_attributes - {session_attr}")
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response

class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        logger.info("inside IntentReflectorHandler()")
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)
        logger.info("inside CatchAllExceptionHandler()")
        speak_output = "Sorry, I had trouble doing what you asked. Please try again."
        logger.info(speak_output)
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

sb = CustomSkillBuilder(persistence_adapter = dynamodb_adapter)

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(PayIntentHandler())
sb.add_request_handler(SetupIntentHandler())
sb.add_request_handler(ChargeIntentHandler())
sb.add_request_handler(RefundOrderIntentHandler())
sb.add_request_handler(CancelOrderIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()

def generateRandomNString(count):
    return ''.join(random.choices(string.ascii_lowercase, k = count))
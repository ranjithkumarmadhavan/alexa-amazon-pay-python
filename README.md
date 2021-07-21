# alexa-amazon-pay-python

**Prerequisites**
1. Amazon developer, AWS account
2. seller central account
3. Amazon pay account

The following are required to start integrating amazon pay with your skill,

1. Get **Merchant ID (Seller ID)**, MWS Access Key ID and MWS Secret Access Key. can find the these credentials in Seller Central on the Amazon Pay and Login with Amazon Integration Settings page (from the Integration menu, click MWS Access Key)
2. **Link your skill** with your Amazon Payments account in Seller Central. 
3. A test user account for testing the payment, which can be created using Amazon Pay (Sandbox View).

**How to use the code?**
1. Copy the lambda code and paste it on your lambda function (python).
2. Make sure you have the aws-sdk library available. You can make use of the layer which I have in my repo.
3. In the environment variable, enter the SANDBOX_CUSTOMER_EMAIL_ID and SELLER_ID.
4. Copy and paste the skill model json to your skill.

**check out** : https://programmerview.com/amazon-pay-integration-with-alexa-using-python/

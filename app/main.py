from __future__ import print_function

from email.utils import make_msgid

from flask import Flask
import json
from flask_cors import CORS
import pickle
import base64
from flask import request
from bs4 import BeautifulSoup

import os.path
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from apiclient import discovery
from httplib2 import Http

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})


# If modifying these scopes, delete the file token.json.


class Mail:
    def __init__(self, subject, sender, body, date):
        self.subject = subject
        self.sender = sender
        self.body = body
        self.date = date


class SentMail:
    def __init__(self, subject, to, body, date):
        self.subject = subject
        self.to = to
        self.body = body
        self.date = date


class GoogleForms:
    def __init__(self, title, documentTitle, url, form):
        self.title = title
        self.documentTitle = documentTitle
        self.url = url
        self.form = form

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class Form:
    def __init__(self, Id, lastSubmitTime, responseName, items):
        self.Id = Id
        self.lastSubmitTime = lastSubmitTime
        self.responseName = responseName
        self.items = items

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class Items:
    def __init__(self, question, answer, typeOfFile):
        self.question = question
        self.answer = answer
        self.typeOfFile = typeOfFile

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=2)


class ItemsWithDoc:
    def __init__(self, question, fileId, fileName, typeOfFile):
        self.question = question
        self.fileId = fileId
        self.fileName = fileName
        self.typeOfFile = typeOfFile

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=2)


def main():
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('credentials-tokens/token.json'):
        creds = Credentials.from_authorized_user_file('credentials-tokens/token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials-tokens/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('credentials-tokens/token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Call the Gmail API
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        if not labels:
            print('No labels found.')
            return
        print('Labels:')
        for label in labels:
            print(label['name'])

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


def getEmails(type):
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    # Variable creds will store the user access token.
    # If no valid token found, we will create one.
    creds = None

    # The file getMailsToken contains the user access token.
    # Check if it exists
    if os.path.exists('credentials-tokens/getMailsToken.pickle'):
        # Read the token from the file and store it in the variable creds
        with open('credentials-tokens/getMailsToken.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If credentials are not available or are invalid, ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials-tokens/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the access token in getMailsToken file for the next run
        with open('credentials-tokens/getMailsToken.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Connect to the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    # request a list of all the messages
    if type == "INBOX":
        result = service.users().messages().list(userId='me', labelIds=['INBOX']).execute()
    else:
        result = service.users().messages().list(userId='me', labelIds=['SENT']).execute()

    # We can also pass maxResults to get any number of emails. Like this:
    # result = service.users().messages().list(maxResults=200, userId='me').execute()
    messages = result.get('messages')

    # messages is a list of dictionaries where each dictionary contains a message id.
    # iterate through all the messages
    returnData = []
    for msg in messages:
        # Get the message from its id
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()

        # Use try-except to avoid any Errors
        try:
            # Get value of 'payload' from dictionary 'txt'
            payload = txt['payload']
            headers = payload['headers']
            subject = ''
            sender = ''
            to = ''
            date = ''
            # Look for Subject and Sender Email in the headers
            if len(list(filter(lambda line: 'Subject' in line['name'], headers))) > 0:
                subject = list(filter(lambda line: 'Subject' in line['name'], headers))[0]['value']
            if type == "INBOX":
                if len(list(filter(lambda line: 'From' in line['name'], headers))) > 0:
                    sender = list(filter(lambda line: 'From' in line['name'], headers))[0]['value']
            else:
                if len(list(filter(lambda line: 'To' in line['name'], headers))) > 0:
                    to = list(filter(lambda line: 'To' in line['name'], headers))[0]['value']
            if len(list(filter(lambda line: 'Date' in line['name'], headers))) > 0:
                date = list(filter(lambda line: 'Date' in line['name'], headers))[0]['value']

            # The Body of the message is in Encrypted format. So, we have to decode it.
            # Get the data and decode it with base 64 decoder.
            if type == "INBOX":
                parts = payload.get('parts')[1]
            else:
                if payload.get('parts') is not None:
                    parts = payload.get('parts')[1]
                else:
                    parts = payload
            data = parts['body']['data']
            data = data.replace("-", "+").replace("_", "/")
            decoded_data = base64.b64decode(data)

            # Now, the data obtained is in lxml. So, we will parse
            # it with BeautifulSoup library
            soup = BeautifulSoup(decoded_data, "lxml")
            body = soup

            # Printing the subject, sender's email and message
            if type == "INBOX":
                Item = Mail(str(subject), str(sender), str(body), str(date))
            else:
                Item = SentMail(str(subject), str(to), str(body), str(date))
            returnData.append(Item)

        except:
            pass
    return json.dumps([obj.__dict__ for obj in returnData]).encode("utf-8")


def gmail_send_message(sender, to, message1, subject):
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    """Create and send an email message
    Print the returned  message id
    Returns: Message object, including message id

    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
    """
    # If no valid token found, we will create one.
    creds = None

    # The file sendMailToken contains the user access token.
    # Check if it exists
    if os.path.exists('credentials-tokens/sendMailToken.pickle'):
        # Read the token from the file and store it in the variable creds
        with open('credentials-tokens/sendMailToken.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If credentials are not available or are invalid, ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials-tokens/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the access token in sendMailToken.pickle file for the next run
        with open('credentials-tokens/sendMailToken.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('gmail', 'v1', credentials=creds)
        message = EmailMessage()
        asparagus_cid = make_msgid()
        message.set_content(message1.format(asparagus_cid=asparagus_cid[1:-1]), subtype='html')
        message['To'] = str(to)
        message['From'] = str(sender)
        message['Subject'] = str(subject)

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()) \
            .decode()

        create_message = {
            'raw': encoded_message
        }
        # pylint: disable=E1101
        send_message = (service.users().messages().send
                        (userId="me", body=create_message).execute())
        print(F'Message Id: {send_message["id"]}')
    except HttpError as error:
        print(F'An error occurred: {error}')
        send_message = None
    return send_message


def getGoogleFormsResponse(formId):
    SCOPES = "https://www.googleapis.com/auth/forms.responses.readonly"
    DISCOVERY_DOC = "https://forms.googleapis.com/$discovery/rest?version=v1"

    # If no valid token found, we will create one.
    creds = None

    # The file getMailsToken contains the user access token.
    # Check if it exists
    if os.path.exists('credentials-tokens/googleFormResponseToken.pickle'):
        # Read the token from the file and store it in the variable creds
        with open('credentials-tokens/googleFormResponseToken.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If credentials are not available or are invalid, ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials-tokens/credentails2.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the access token in sendMailToken.pickle file for the next run
        with open('credentials-tokens/googleFormResponseToken.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('forms', 'v1', credentials=creds)

    # Prints the responses of your specified form:
    form_id = '<YOUR_FORM_ID>'
    resultForm = getGoogleForm(formId)
    result = service.forms().responses().list(formId=formId).execute()

    list1 = []
    i = 0
    for form in result['responses']:
        listItem = []
        for ans in form['answers']:
            res = list(filter(lambda line: ans in line['questionItem']['question']['questionId'], resultForm['items']))
            question = res[0]['title']
            if 'textAnswers' in form['answers'][ans]:
                answer = form['answers'][ans]['textAnswers']['answers'][0]['value']
                Item = Items(question, answer, "textAnswers")
                listItem.append(Item)
            else:
                answer = form['answers'][ans]['fileUploadAnswers']['answers'][0]
                field = answer['fileId']
                fileName = answer['fileName']
                ItemWithDoc = ItemsWithDoc(question, field, fileName, "FileUploadAnswers")
                listItem.append(ItemWithDoc)
        i += 1;
        ItemFrom = Form(i, form['lastSubmittedTime'], 'Response ' + str(i), listItem)
        list1.append(ItemFrom)
    googleForms = GoogleForms(resultForm['info']['title'], resultForm['info']['documentTitle'],
                              resultForm['responderUri'], list1)
    return googleForms.toJSON().encode("utf-8")


def getGoogleForm(formId):
    SCOPES = "https://www.googleapis.com/auth/forms.body.readonly"

    # If no valid token found, we will create one.
    creds = None

    # The file sendMailToken contains the user access token.

    if os.path.exists('credentials-tokens/googleFormToken.pickle'):
        # Read the token from the file and store it in the variable creds
        with open('credentials-tokens/googleFormToken.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If credentials are not available or are invalid, ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials-tokens/credentails2.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the access token in sendMailToken.pickle file for the next run
        with open('credentials-tokens/googleFormToken.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('forms', 'v1', credentials=creds)

    # Prints the responses of your specified form:
    form_id = '<YOUR_FORM_ID>'
    result = service.forms().get(formId=formId).execute()
    return result


@app.route("/api/getInboxList")
def inbox():
    return getEmails("INBOX")


@app.route("/api/getSentList")
def sentMails():
    return getEmails("SENT")


@app.route("/api/getGoogleForms", methods=['POST'])
def getGoogleForms():
    return getGoogleFormsResponse(request.get_json()['formId'])


@app.route("/api/sendMail", methods=['POST'])
def sendMail():
    print(request.get_json()['sender'])
    gmail_send_message(request.get_json()['sender'], request.get_json()['to'], request.get_json()['message'],
                       request.get_json()['subject'])
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


@app.route("/api")
def hello():
    return "Hello World from Flask in a uWSGI Nginx Docker container with Gmail Api"


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host="0.0.0.0", debug=True, port=5000)

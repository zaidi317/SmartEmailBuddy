from flask import Flask, render_template, request, redirect, url_for, jsonify
import imaplib
import email
import email as email_module
from email.header import decode_header
from bs4 import BeautifulSoup
import requests
import re
import quopri
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import nltk
from nltk import word_tokenize
from nltk.corpus import stopwords

app = Flask(__name__)

# Initialize NLTK (download required packages if not already downloaded)
nltk.download('punkt')
nltk.download('stopwords')

# User credentials (replace with your email and password)
USER_CREDENTIALS = {'email': 'mariumf435@gmail.com', 'password': 'wrtg pnty hmhu ezzq'}

# Load tokenizer and model for summarization
tokenizer = AutoTokenizer.from_pretrained("t5-base")
model = AutoModelForSeq2SeqLM.from_pretrained("t5-base")
summarizer = pipeline("summarization", model=model, tokenizer=tokenizer)

# Preprocess the email content
def preprocess_text(text):
    # Tokenize the text
    tokens = word_tokenize(text.lower())

    # Remove stopwords and non-alphanumeric tokens
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [token for token in tokens if token.isalnum() and token not in stop_words]

    return filtered_tokens

# Function to generate a response based on email content
def generate_response(body, sender_name):
    # Add your logic to generate a response based on the content of the email
    # For demonstration, let's just return a static response
    if "urgent" in body.lower():
        return f"This is an urgent matter, {sender_name}. We will escalate it and get back to you shortly."
    elif "help" in body.lower():
        return f"Sure, {sender_name}, we are here to help. Please provide more details about your issue."
    else:
        return f"Thank you for your email, {sender_name}. We will get back to you shortly."
# Function to decode email headers

# Function to fetch unread emails and generate responses
def fetch_and_generate_responses():
    try:
        # Connect to Gmail's IMAP server
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(USER_CREDENTIALS['email'], USER_CREDENTIALS['password'])
        mail.select('inbox')

        # Search for all messages
        status, messages = mail.search(None, 'ALL')  # Fetch all emails, not just unread ones
        mail_ids = messages[0].split()

        responses = []
        for num in mail_ids:
            try:
                # Fetch email
                status, data = mail.fetch(num, '(RFC822)')
                raw_email = data[0][1]
                email_message = email.message_from_bytes(raw_email)

                # Extract email content
                subject = decode_header(email_message['Subject'])[0][0]
                sender = email_message['From']
                sender_name = re.findall('"([^"]*)"', sender)[0]
                body = ""

                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()

                        if content_type == 'text/plain':
                            body = part.get_payload(decode=True).decode()

                else:
                    body = email_message.get_payload(decode=True).decode()

                print(f"Fetched email from {sender} with subject: {subject}")  # Add this line

                # Generate a response based on email content
                response_text = generate_response(body, sender_name)
                responses.append({
                    'sender': sender,
                    'subject': subject,
                    'response': response_text
                })

            except IndexError:
                print("Error processing email: list index out of range")
            except Exception as e:
                print(f"Error processing email: {e}")

        # Close IMAP connection
        mail.close()
        mail.logout()

        print(f"Fetched {len(responses)} emails.")
        return responses

    except Exception as e:
        print(f"Error fetching emails: {e}")
        return []

def decode_email_header(header):
    decoded_header = []
    for part, charset in decode_header(header):
        if isinstance(part, bytes):
            if charset:
                decoded_header.append(part.decode(charset))
            else:
                decoded_header.append(part.decode())
        else:
            decoded_header.append(part)
    return ' '.join(decoded_header)

# Function to extract email body from multipart content and format it for display
def extract_email_body(message):
    if message.is_multipart():
        # If the message is multipart, recursively extract the body from its parts
        parts = []
        for part in message.get_payload():
            extracted_part = extract_email_body(part)
            if extracted_part is not None:
                parts.append(extracted_part)
        if parts:
            return '\n'.join(parts)
        else:
            return None
    else:
        # Attempt to decode the payload using multiple encodings
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
            try:
                body = message.get_payload(decode=True).decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            # If all decoding attempts fail, handle the error gracefully
            try:
                # Try decoding using quoted-printable
                body = quopri.decodestring(message.get_payload()).decode('utf-8')
            except:
                # If decoding using quoted-printable also fails, set the body to None
                body = None
                print("Unable to decode email body for message:")
                print(message)

        if body is not None:
            # Remove HTML tags
            text = BeautifulSoup(body, 'html.parser').get_text()
            # Remove extra line breaks and multiple spaces
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r'\s{2,}', ' ', text)
            return text
        else:
            return None

# Function to fetch emails using imaplib
def fetch_emails():
    # Establish IMAP connection
    imap_conn = imaplib.IMAP4_SSL('imap.gmail.com')
    imap_conn.login(USER_CREDENTIALS['email'], USER_CREDENTIALS['password'])

    # Select the INBOX folder
    imap_conn.select('INBOX')

    # Search for all emails
    typ, data = imap_conn.search(None, 'ALL')

    # Limit the number of emails fetched (fetch first 10 emails)
    email_ids = data[0].split()[-10:]

    emails = []
    # Fetch email details for each ID
    for email_id in email_ids:
        typ, email_data = imap_conn.fetch(email_id, '(RFC822)')
        raw_email = email_data[0][1]
        parsed_email = email_module.message_from_bytes(raw_email)

        # Check if the email has image attachments
        has_image_attachment = False
        for part in parsed_email.walk():
            content_type = part.get_content_type()
            if content_type.startswith('image'):
                has_image_attachment = True
                break

        # Extract the email body if it doesn't have image attachments
        if not has_image_attachment:
            body = extract_email_body(parsed_email)
            if body is not None:
                # Summarize email content
                summary = summarize_email_content(body)
                email_dict = {
                    'From': decode_email_header(parsed_email['From']),
                    'To': decode_email_header(parsed_email['To']),
                    'Subject': decode_email_header(parsed_email['Subject']),
                    'Date': decode_email_header(parsed_email['Date']),
                    'Body': body,
                    'Summary': summary  # Add summary here
                }
                emails.append(email_dict)

    # Close IMAP connection
    imap_conn.close()
    imap_conn.logout()

    return emails

# Function to summarize email content
def summarize_email_content(email_content):
    try:
        # Summarize email content
        summary = summarizer(email_content, max_length=150, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing email content: {e}")
        return None

# Function to fetch unsubscribe emails
def fetch_unsubscribe_emails():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(USER_CREDENTIALS['email'], USER_CREDENTIALS['password'])
    mail.select('inbox')

    unsubscribe_emails = []

    status, messages = mail.search(None, 'ALL')
    for num in messages[0].split():
        status, msg = mail.fetch(num, '(RFC822)')
        raw_message = msg[0][1]
        email_message = email.message_from_bytes(raw_message)

        for part in email_message.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload(decode=True)
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    if 'unsubscribe' in link.text.lower():
                        unsubscribe_emails.append({
                            'From': email_message['From'],
                            'Subject': email_message['Subject'],
                            'Unsubscribe_Link': link['href']
                        })
                        break

    mail.close()
    mail.logout()
    return unsubscribe_emails

# Function to unsubscribe from emails
def unsubscribe_from_emails(emails):
    for email in emails:
        unsubscribe_link = email['Unsubscribe_Link']
        try:
            response = requests.get(unsubscribe_link, headers={'User-Agent': 'Your App Name'})
            if response.status_code == 200:
                print(f'Unsubscribed from {email["From"]} ({email["Subject"]})')
            else:
                print(f'Failed to unsubscribe from {email["From"]} ({email["Subject"]}): {response.status_code}')
        except requests.RequestException as e:
            print(f'Error: Failed to unsubscribe from {email["From"]} ({email["Subject"]}). {e}')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Check if the entered credentials match the user credentials
        if request.form['email'] == USER_CREDENTIALS['email'] and request.form['password'] == USER_CREDENTIALS['password']:
            # If the credentials are correct, redirect to the index page
            return redirect(url_for('index'))
        else:
            # If the credentials are incorrect, render the login page again with an error message
            return render_template('login.html', error='Invalid email or password')
    # Render the login page for GET requests
    return render_template('login.html')

@app.route('/generate_responses', methods=['GET'])
def generate_responses():
    # Fetch unread emails and generate responses
    responses = fetch_and_generate_responses()
    print(responses)  # Add this line to check if responses are being fetched
    return render_template('responses.html', responses=responses)

@app.route('/send_response', methods=['POST'])
def send_response():
    if request.method == 'POST':
        response_text = request.form['response_text']
        recipient_email = request.form['recipient_email']
        # Here you would send the email with the response_text to the recipient_email
        # For demonstration, let's print the details
        print(f"Response Text: {response_text}")
        print(f"Recipient Email: {recipient_email}")
        return jsonify({'message': 'Response sent successfully.'})

# Route to display unsubscribe form
@app.route('/unsubscribe', methods=['GET'])
def display_unsubscribe_form():
    unsubscribe_emails = fetch_unsubscribe_emails()
    return render_template('unsubscribe.html', emails=unsubscribe_emails)

@app.route('/index')
def index():
    # Fetch emails for the authenticated user
    emails = fetch_emails()
    return render_template('index.html', emails=emails)

@app.route('/summary')
def summary():
    # Fetch emails for the authenticated user
    emails = fetch_emails()
    return render_template('summary.html', emails=emails)

# Route to handle unsubscribe request
@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    choice = request.form.get('choice')
    if choice == 'yes':
        unsubscribe_emails = fetch_unsubscribe_emails()
        unsubscribe_from_emails(unsubscribe_emails)
        return render_template('success.html', message="Unsubscribe successful. Thank you!")
    elif choice == 'no':
        return render_template('cancel.html', message="Unsubscribe cancelled. No action taken.")
    else:
        return "Invalid choice."

@app.route('/unsubscribe/success')
def unsubscribe_success():
    return render_template('success.html', message="Unsubscribe successful. Thank you!")

@app.route('/unsubscribe/cancel')
def unsubscribe_cancel():
    return render_template('cancel.html', message="Unsubscribe cancelled. No action taken.")

if __name__ == '__main__':
    app.run(debug=True)

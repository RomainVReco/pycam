import smtplib
import ssl
import json
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from email.utils import formatdate


class GenerateMail(object):

    def __new__(self):
        self.smtp_server = ""
        self.smtp_port = None
        self.email_sender = ""
        self.email_receiver = ""
        self.smtp_password = ""
        self.SUBJECT = "Mouvement détecté"
        self.message = None
        if not hasattr(self, 'instance'):
            self.instance = super(GenerateMail, self).__new__(self)
        return self.instance


    def prepare_singleton(self):
        with open("config_mail.json") as config:
            gmail_cfg = json.load(config)
#        json_file = open("/home/romain/Python_scripts/pycam/config_mail.json")
#        gmail_cfg = json.load(json_file)
        self.smtp_server = gmail_cfg["server"]
        self.email_sender = gmail_cfg["from"]
        self.email_receiver = gmail_cfg["to"]
        self.smtp_password = gmail_cfg["password"]
        self.smtp_port = gmail_cfg["port"]


    def prepare_mail(self, file_name):
        self.message = MIMEMultipart('alternative')
        self.message['Subject'] = self.SUBJECT
        self.message['From'] = self.email_sender
        self.message['To'] = self.email_receiver
        self.message.attach(MIMEText('Un mouvement a été détecté dans la pièce', 'plain'))
        with open(file_name, 'rb') as attachment:
            file_part = MIMEBase('application', 'octet-stream')
            file_part.set_payload(attachment.read())
            encoders.encode_base64(file_part)
            file_part.add_header(
            'Content-Disposition',
            'attachment; filename='+ str(file_name)
            )
            self.message.attach(file_part)



    def send_mail(self):
        print("Initiation envoi mail")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context = context) as server:
            server.login(self.email_sender, self.smtp_password)
            result = server.sendmail(self.email_sender, self.email_receiver, self.message.as_string())
            print("Envoi mail : ", result)


    def remove_message(self):
        self.message = None

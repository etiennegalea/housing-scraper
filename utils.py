def notifify_email(func):
    def wrapper():
        
        message = Mail(
            from_email = "pitirross.life@gmail.com",
            to_emails = to_email,
            subject = content[0],
            html_content = content[1]
        )
        try:
            sg = SendGridAPIClient(self.SENDGRID_API_KEY)
            response = sg.send(message)

        return response.status_code
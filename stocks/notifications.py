import smtplib
from email.mime.text import MIMEText
from django.conf import settings
from .models import LiveTrade

def send_email_notification(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = settings.NOTIFICATION_EMAIL

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

def check_sl_tp_triggers():
    trades = LiveTrade.objects.filter(status="Executed")
    for trade in trades:
        live_price = BreezeAPI().get_live_price(trade.stock_code, trade.exchange)

        if trade.stop_loss and live_price <= trade.stop_loss:
            send_email_notification(f"Stop-Loss Hit for {trade.stock_code}", "Your trade has exited at Stop-Loss price.")
        
        if trade.take_profit and live_price >= trade.take_profit:
            send_email_notification(f"Take-Profit Hit for {trade.stock_code}", "Your trade has exited at Take-Profit price.")

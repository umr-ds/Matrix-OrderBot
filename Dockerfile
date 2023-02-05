FROM python:3.8

ADD orderbot/util.py .
ADD orderbot/orderbot.py .
ADD orderbot/order.py .
ADD orderbot/order_parser.py .
ADD orderbot/db_classes.py .

COPY requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "-u", "./orderbot.py"]
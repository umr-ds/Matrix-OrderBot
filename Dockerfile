FROM python:3.8

RUN pip install matrix-orderbot

CMD ["orderbot"]
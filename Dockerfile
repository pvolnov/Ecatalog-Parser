FROM python:3.7


WORKDIR /home/petr/Documents/Projects/Ikea

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install --upgrade pip
RUN venv/bin/pip install -r requirements.txt

COPY bot bot
COPY bot.py config.py updater ./

ENTRYPOINT ["venv/bin/python","bot.py"]
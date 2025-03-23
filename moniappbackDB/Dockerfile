FROM python
RUN mkdir /backmoniapp
RUN chmod 777 /backmoniapp
COPY . /backmoniapp
WORKDIR /backmoniapp
RUN apt update && apt install vim -y
RUN pip install -r requirements.txt
CMD ["python", "app.py"]

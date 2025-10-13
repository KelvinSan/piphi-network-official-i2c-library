FROM python:3.12-slim

RUN mkdir /integration

COPY requirements.txt ./integration/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /integration/requirements.txt

RUN ls

COPY ./ /integration

WORKDIR /integration

EXPOSE 3669

CMD ["fastapi", "run", "/integration/src/piphi-network-official-i2c-library/app.py", "--port", "3669"]
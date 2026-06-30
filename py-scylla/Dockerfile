FROM python:3.14

WORKDIR /app

RUN apt-get update && apt-get install -y \
  gcc \
  python3-dev \
  libev4 \
  libev-dev \
  libevent-dev \
  build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN pip install pandas
RUN pip install scylla-driver
RUN pip install faker
RUN pip install matplotlib
RUN pip install numpy
RUN pip install scikit-learn
RUN pip install seaborn
RUN pip install prettytable
RUN pip install pyyaml
RUN pip install pydantic
RUN pip install mimesis

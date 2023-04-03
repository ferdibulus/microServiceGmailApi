FROM tiangolo/uwsgi-nginx-flask:python3.8

COPY app /app
RUN pip install Flask \
    && pip install APScheduler \
    && pip install -U flask-cors \
    && pip install pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib \
    && pip install beautifulsoup4 \
    && pip install lxml \
    && pip install

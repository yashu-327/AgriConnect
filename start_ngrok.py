from pyngrok import ngrok

t = ngrok.connect(8000, bind_tls=True)
print(t.public_url)
# keep script running briefly to ensure ngrok process stays alive
import time
time.sleep(1)

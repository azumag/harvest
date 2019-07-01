deploy

```
 gcloud datastore indexes create ./index.yaml

 gcloud beta functions deploy master --trigger-http --runtime nodejs8 --memory 128

 gcloud beta functions deploy agent --trigger-resource agent --trigger-event google.pubsub.topic.publish --runtime python37 --env-vars-file .env.yaml --memory 256 
```
deprecated:
```
mv .env.example .env # [Please edit .env with your environments]
docker-compose up --scale agent=10 agent
```

const axios = require('axios');
const { Datastore } = require('@google-cloud/datastore');
const { PubSub } = require('@google-cloud/pubsub');

const datastore = new Datastore();
const pubsub = new PubSub();

exports.master = (req, res) => {
  // invoke each individuals strategy
  const query = datastore.createQuery('Individual')
    .filter('life', '=', 'alive');
  datastore.runQuery(query)
  .then(([data]) => {
    data.forEach((indv) => {
      console.log(indv);
      publishMessage(indv);
    });
    res.status(200);
    res.end();
  });
}

async function publishMessage(individual) {
  individual['id'] = individual[datastore.KEY].id;
  const topicName = individual.strategy;
  const dataBuffer = Buffer.from(JSON.stringify(individual));
  await pubsub.topic(topicName).publish(dataBuffer);
}
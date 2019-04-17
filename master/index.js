const axios = require('axios');
const { Datastore } = require('@google-cloud/datastore');
const { PubSub } = require('@google-cloud/pubsub');

const datastore = new Datastore();
const pubsub = new PubSub();

const exchangers = ['bitbank']
const symbols = ['BTC/JPY', 'XRP/JPY', 'MONA/JPY', 'BCH/JPY']
const numIndividuals = 25

exports.master = (req, res) => {
  // invoke each individuals strategy
  // alive entities
  const query = datastore.createQuery('Individual')
    .filter('life', '>=', 0);
  datastore.runQuery(query)
  .then(([data]) => {
    // console.log(data)
    data.forEach((indv) => {
      console.log(indv);
      if (indv.life === 0 && indv.total_profit > 0) {
        cloneIndividual(indv);
      }
      publishMessage(indv);
    });
    if (data.length <= numIndividuals) {
      for (var i = 0; i < numIndividuals; i++) {
        newRandomIndividual()
      }
    }
    res.status(200);
    res.end();
  });
}


exports.createRandomIndividual = (req, res) => {
  newRandomIndividual()
  res.status(200);
  res.end();
}

function getRandomInt(max) {
  return Math.floor(Math.random() * Math.floor(max));
}

function normRand(m, s) {
  var a = 1 - Math.random();
  var b = 1 - Math.random();
  var c = Math.sqrt(-2 * Math.log(a));
  if (0.5 - Math.random() > 0) {
    return c * Math.sin(Math.PI * 2 * b) * s + m;
  } else {
    return c * Math.cos(Math.PI * 2 * b) * s + m;
  }
};

async function cloneIndividual(indv) {
  indv.life = indv.lifespan;
  indv.total_profit = 0.0;
  saveIndividual(indv)
  saveIndividual(indv)
}

function newRandomIndividual() {
  const life = Math.abs(Math.floor(normRand(100, 100)))
  const strategies = {
    'dongchang': {
      life,
      lifespan: life,
      payment: Math.abs(0.0001*normRand(100, 100)),
      period_buy: Math.abs(Math.floor(normRand(40, 40))),
      period_sell: Math.abs(Math.floor(normRand(20, 20))),
      total_profit: 0.0,
      exchanger: exchangers[getRandomInt(exchangers.length)],
      symbol: symbols[getRandomInt(symbols.length)],
      strategy: 'dongchang',
      state: 'neutral'
    },
    'ema': {
      life,
      lifespan: life,
      payment: Math.abs(0.0001*normRand(100, 100)),
      period: Math.abs(Math.floor(normRand(26, 26))),
      limit : Math.abs(Math.floor(normRand(10000, 10000))),
      total_profit: 0.0,
      exchanger: exchangers[getRandomInt(exchangers.length)],
      symbol: symbols[getRandomInt(symbols.length)],
      decision_rate_up: (0.00000001*normRand(10000, 10000)),
      decision_rate_down: (0.00000001*normRand(10000, 10000)),
      strategy: 'ema',
      state: 'neutral'
    },
  }


  const strategy_names = Object.keys(strategies);
  const strategy_name = strategy_names[getRandomInt(strategy_names.length)]
  console.log(strategy_name)
  const individual = strategies[strategy_name]


  saveIndividual(individual)
}

async function saveIndividual(individual) {
  const key = datastore.key('Individual');
  const entity = {
    key,
    data: Object.assign(individual, { created_at: new Date() }),
  };

  return await datastore.insert(entity).then(() => {
    console.log('ok')
    return 'ok'
  }).catch(error => {
    console.log(error)
    return error
  });
}

async function publishMessage(individual) {
  individual['id'] = individual[datastore.KEY].id;
  // const topicName = individual.strategy;
  const topicName = 'agent';
  const dataBuffer = Buffer.from(JSON.stringify(individual));
  await pubsub.topic(topicName).publish(dataBuffer);
}
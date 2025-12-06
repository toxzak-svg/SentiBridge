import { BigInt, Bytes } from "@graphprotocol/graph-ts";

import {
  SentimentUpdated,
  TokenWhitelisted,
  TokenDelisted,
  CircuitBreakerTriggered,
  OperatorUpdated,
  Paused,
  Unpaused,
} from "../generated/SentimentOracle/SentimentOracle";

import {
  Token,
  SentimentUpdate,
  DailySentiment,
  HourlySentiment,
  CircuitBreakerEvent,
  Operator,
  OracleStats,
} from "../generated/schema";

// Constants
const HOUR_SECONDS = BigInt.fromI32(3600);
const DAY_SECONDS = BigInt.fromI32(86400);
const STATS_ID = "stats";

// Helper functions
function getOrCreateToken(symbol: string): Token {
  let token = Token.load(symbol);
  
  if (token == null) {
    token = new Token(symbol);
    token.currentScore = BigInt.fromI32(5000); // Neutral default
    token.currentVolume = BigInt.fromI32(0);
    token.lastUpdated = BigInt.fromI32(0);
    token.isWhitelisted = false;
    token.updateCount = BigInt.fromI32(0);
  }
  
  return token;
}

function getOrCreateStats(): OracleStats {
  let stats = OracleStats.load(STATS_ID);
  
  if (stats == null) {
    stats = new OracleStats(STATS_ID);
    stats.totalTokens = BigInt.fromI32(0);
    stats.activeTokens = BigInt.fromI32(0);
    stats.totalUpdates = BigInt.fromI32(0);
    stats.isPaused = false;
    stats.lastUpdate = BigInt.fromI32(0);
    stats.circuitBreakerTriggers = BigInt.fromI32(0);
  }
  
  return stats;
}

function getOrCreateOperator(address: string): Operator {
  let operator = Operator.load(address);
  
  if (operator == null) {
    operator = new Operator(address);
    operator.isActive = false;
    operator.addedAt = BigInt.fromI32(0);
    operator.removedAt = null;
    operator.updateCount = BigInt.fromI32(0);
  }
  
  return operator;
}

function getDayId(tokenSymbol: string, timestamp: BigInt): string {
  let dayTimestamp = timestamp.div(DAY_SECONDS).times(DAY_SECONDS);
  return tokenSymbol + "-" + dayTimestamp.toString();
}

function getHourId(tokenSymbol: string, timestamp: BigInt): string {
  let hourTimestamp = timestamp.div(HOUR_SECONDS).times(HOUR_SECONDS);
  return tokenSymbol + "-" + hourTimestamp.toString();
}

function getOrCreateDailySentiment(token: Token, timestamp: BigInt): DailySentiment {
  let dayTimestamp = timestamp.div(DAY_SECONDS).times(DAY_SECONDS);
  let id = getDayId(token.id, timestamp);
  let daily = DailySentiment.load(id);
  
  if (daily == null) {
    daily = new DailySentiment(id);
    daily.token = token.id;
    daily.dayTimestamp = dayTimestamp;
    daily.averageScore = BigInt.fromI32(0);
    daily.highScore = BigInt.fromI32(0);
    daily.lowScore = BigInt.fromI32(10000);
    daily.openScore = BigInt.fromI32(0);
    daily.closeScore = BigInt.fromI32(0);
    daily.totalVolume = BigInt.fromI32(0);
    daily.updateCount = BigInt.fromI32(0);
  }
  
  return daily;
}

function getOrCreateHourlySentiment(token: Token, timestamp: BigInt): HourlySentiment {
  let hourTimestamp = timestamp.div(HOUR_SECONDS).times(HOUR_SECONDS);
  let id = getHourId(token.id, timestamp);
  let hourly = HourlySentiment.load(id);
  
  if (hourly == null) {
    hourly = new HourlySentiment(id);
    hourly.token = token.id;
    hourly.hourTimestamp = hourTimestamp;
    hourly.averageScore = BigInt.fromI32(0);
    hourly.highScore = BigInt.fromI32(0);
    hourly.lowScore = BigInt.fromI32(10000);
    hourly.totalVolume = BigInt.fromI32(0);
    hourly.updateCount = BigInt.fromI32(0);
  }
  
  return hourly;
}

// Event Handlers
export function handleSentimentUpdated(event: SentimentUpdated): void {
  let tokenSymbol = event.params.tokenSymbol;
  let score = event.params.score;
  let volume = event.params.volume;
  let sourceHash = event.params.sourceHash;
  let timestamp = event.block.timestamp;
  
  // Update token
  let token = getOrCreateToken(tokenSymbol);
  token.currentScore = score;
  token.currentVolume = volume;
  token.lastUpdated = timestamp;
  token.updateCount = token.updateCount.plus(BigInt.fromI32(1));
  token.save();
  
  // Create sentiment update entity
  let updateId = event.transaction.hash.toHexString() + "-" + event.logIndex.toString();
  let update = new SentimentUpdate(updateId);
  update.token = token.id;
  update.score = score;
  update.volume = volume;
  update.sourceHash = sourceHash;
  update.blockNumber = event.block.number;
  update.timestamp = timestamp;
  update.transactionHash = event.transaction.hash;
  update.save();
  
  // Update daily aggregation
  let daily = getOrCreateDailySentiment(token, timestamp);
  
  if (daily.updateCount.equals(BigInt.fromI32(0))) {
    daily.openScore = score;
  }
  daily.closeScore = score;
  
  if (score.gt(daily.highScore)) {
    daily.highScore = score;
  }
  if (score.lt(daily.lowScore)) {
    daily.lowScore = score;
  }
  
  // Calculate running average
  let totalScore = daily.averageScore.times(daily.updateCount).plus(score);
  daily.updateCount = daily.updateCount.plus(BigInt.fromI32(1));
  daily.averageScore = totalScore.div(daily.updateCount);
  daily.totalVolume = daily.totalVolume.plus(volume);
  daily.save();
  
  // Update hourly aggregation
  let hourly = getOrCreateHourlySentiment(token, timestamp);
  
  if (score.gt(hourly.highScore)) {
    hourly.highScore = score;
  }
  if (score.lt(hourly.lowScore)) {
    hourly.lowScore = score;
  }
  
  let hourlyTotalScore = hourly.averageScore.times(hourly.updateCount).plus(score);
  hourly.updateCount = hourly.updateCount.plus(BigInt.fromI32(1));
  hourly.averageScore = hourlyTotalScore.div(hourly.updateCount);
  hourly.totalVolume = hourly.totalVolume.plus(volume);
  hourly.save();
  
  // Update global stats
  let stats = getOrCreateStats();
  stats.totalUpdates = stats.totalUpdates.plus(BigInt.fromI32(1));
  stats.lastUpdate = timestamp;
  stats.save();
}

export function handleTokenWhitelisted(event: TokenWhitelisted): void {
  let tokenSymbol = event.params.tokenSymbol;
  
  let token = getOrCreateToken(tokenSymbol);
  
  // If this is a new token, increment total count
  let isNew = !token.isWhitelisted && token.updateCount.equals(BigInt.fromI32(0));
  
  token.isWhitelisted = true;
  token.save();
  
  let stats = getOrCreateStats();
  if (isNew) {
    stats.totalTokens = stats.totalTokens.plus(BigInt.fromI32(1));
  }
  stats.activeTokens = stats.activeTokens.plus(BigInt.fromI32(1));
  stats.save();
}

export function handleTokenDelisted(event: TokenDelisted): void {
  let tokenSymbol = event.params.tokenSymbol;
  
  let token = getOrCreateToken(tokenSymbol);
  token.isWhitelisted = false;
  token.save();
  
  let stats = getOrCreateStats();
  stats.activeTokens = stats.activeTokens.minus(BigInt.fromI32(1));
  stats.save();
}

export function handleCircuitBreakerTriggered(event: CircuitBreakerTriggered): void {
  let tokenSymbol = event.params.tokenSymbol;
  let previousScore = event.params.previousScore;
  let attemptedScore = event.params.attemptedScore;
  let maxChange = event.params.maxChange;
  
  let token = getOrCreateToken(tokenSymbol);
  
  let eventId = event.transaction.hash.toHexString() + "-" + event.logIndex.toString();
  let cbEvent = new CircuitBreakerEvent(eventId);
  cbEvent.token = token.id;
  cbEvent.previousScore = previousScore;
  cbEvent.attemptedScore = attemptedScore;
  cbEvent.maxChange = maxChange;
  cbEvent.timestamp = event.block.timestamp;
  cbEvent.transactionHash = event.transaction.hash;
  cbEvent.save();
  
  let stats = getOrCreateStats();
  stats.circuitBreakerTriggers = stats.circuitBreakerTriggers.plus(BigInt.fromI32(1));
  stats.save();
}

export function handleOperatorUpdated(event: OperatorUpdated): void {
  let oldOperator = event.params.oldOperator;
  let newOperator = event.params.newOperator;
  let timestamp = event.block.timestamp;
  
  // Deactivate old operator
  if (oldOperator.toHexString() != "0x0000000000000000000000000000000000000000") {
    let old = getOrCreateOperator(oldOperator.toHexString());
    old.isActive = false;
    old.removedAt = timestamp;
    old.save();
  }
  
  // Activate new operator
  let operator = getOrCreateOperator(newOperator.toHexString());
  operator.isActive = true;
  operator.addedAt = timestamp;
  operator.removedAt = null;
  operator.save();
}

export function handlePaused(event: Paused): void {
  let stats = getOrCreateStats();
  stats.isPaused = true;
  stats.save();
}

export function handleUnpaused(event: Unpaused): void {
  let stats = getOrCreateStats();
  stats.isPaused = false;
  stats.save();
}

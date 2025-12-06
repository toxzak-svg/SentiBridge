import { BigInt, Address } from "@graphprotocol/graph-ts";

import {
  SentimentUpdated,
  TokenWhitelisted,
  CircuitBreakerTriggered,
  Paused,
  Unpaused,
} from "../generated/SentimentOracle/SentimentOracle";

import {
  Token,
  SentimentUpdate,
  DailySentiment,
  HourlySentiment,
  CircuitBreakerEvent,
  OracleStats,
} from "../generated/schema";

// Constants
const HOUR_SECONDS = BigInt.fromI32(3600);
const DAY_SECONDS = BigInt.fromI32(86400);
const STATS_ID = "stats";
const MIN_SCORE = BigInt.fromString("-1000000000000000000");
const MAX_SCORE = BigInt.fromString("1000000000000000000");

// Helper functions
function getOrCreateToken(address: Address): Token {
  let id = address.toHexString();
  let token = Token.load(id);
  
  if (token == null) {
    token = new Token(id);
    token.address = address;
    token.currentScore = BigInt.fromI32(0);
    token.currentConfidence = 0;
    token.currentSampleSize = 0;
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

function getDayId(tokenId: string, timestamp: BigInt): string {
  let dayTimestamp = timestamp.div(DAY_SECONDS).times(DAY_SECONDS);
  return tokenId + "-" + dayTimestamp.toString();
}

function getHourId(tokenId: string, timestamp: BigInt): string {
  let hourTimestamp = timestamp.div(HOUR_SECONDS).times(HOUR_SECONDS);
  return tokenId + "-" + hourTimestamp.toString();
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
    daily.highScore = MIN_SCORE;
    daily.lowScore = MAX_SCORE;
    daily.openScore = BigInt.fromI32(0);
    daily.closeScore = BigInt.fromI32(0);
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
    hourly.highScore = MIN_SCORE;
    hourly.lowScore = MAX_SCORE;
    hourly.updateCount = BigInt.fromI32(0);
  }
  
  return hourly;
}

// Event Handlers
export function handleSentimentUpdated(event: SentimentUpdated): void {
  let tokenAddress = event.params.token;
  let score = event.params.score;
  let confidence = event.params.confidence;  // i32
  let sampleSize = event.params.sampleSize;  // BigInt
  let blockTimestamp = event.block.timestamp;
  
  // Update token
  let token = getOrCreateToken(tokenAddress);
  token.currentScore = score;
  token.currentConfidence = confidence;
  token.currentSampleSize = sampleSize.toI32();  // Convert BigInt to i32
  token.lastUpdated = blockTimestamp;
  token.updateCount = token.updateCount.plus(BigInt.fromI32(1));
  token.save();
  
  // Create sentiment update entity
  let updateId = event.transaction.hash.toHexString() + "-" + event.logIndex.toString();
  let update = new SentimentUpdate(updateId);
  update.token = token.id;
  update.score = score;
  update.confidence = confidence;
  update.sampleSize = sampleSize.toI32();  // Convert BigInt to i32
  update.blockNumber = event.block.number;
  update.timestamp = blockTimestamp;
  update.transactionHash = event.transaction.hash;
  update.save();
  
  // Update daily aggregation
  let daily = getOrCreateDailySentiment(token, blockTimestamp);
  
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
  daily.save();
  
  // Update hourly aggregation
  let hourly = getOrCreateHourlySentiment(token, blockTimestamp);
  
  if (score.gt(hourly.highScore)) {
    hourly.highScore = score;
  }
  if (score.lt(hourly.lowScore)) {
    hourly.lowScore = score;
  }
  
  let hourlyTotalScore = hourly.averageScore.times(hourly.updateCount).plus(score);
  hourly.updateCount = hourly.updateCount.plus(BigInt.fromI32(1));
  hourly.averageScore = hourlyTotalScore.div(hourly.updateCount);
  hourly.save();
  
  // Update global stats
  let stats = getOrCreateStats();
  stats.totalUpdates = stats.totalUpdates.plus(BigInt.fromI32(1));
  stats.lastUpdate = blockTimestamp;
  stats.save();
}

export function handleTokenWhitelisted(event: TokenWhitelisted): void {
  let tokenAddress = event.params.token;
  let status = event.params.status;
  
  let token = getOrCreateToken(tokenAddress);
  
  // If this is a new token being whitelisted, increment total count
  let isNew = !token.isWhitelisted && token.updateCount.equals(BigInt.fromI32(0));
  
  let stats = getOrCreateStats();
  
  if (status) {
    // Token is being whitelisted
    token.isWhitelisted = true;
    if (isNew) {
      stats.totalTokens = stats.totalTokens.plus(BigInt.fromI32(1));
    }
    stats.activeTokens = stats.activeTokens.plus(BigInt.fromI32(1));
  } else {
    // Token is being delisted
    token.isWhitelisted = false;
    stats.activeTokens = stats.activeTokens.minus(BigInt.fromI32(1));
  }
  
  token.save();
  stats.save();
}

export function handleCircuitBreakerTriggered(event: CircuitBreakerTriggered): void {
  let tokenAddress = event.params.token;
  let reason = event.params.reason;
  
  let token = getOrCreateToken(tokenAddress);
  
  let eventId = event.transaction.hash.toHexString() + "-" + event.logIndex.toString();
  let cbEvent = new CircuitBreakerEvent(eventId);
  cbEvent.token = token.id;
  cbEvent.reason = reason;
  cbEvent.timestamp = event.block.timestamp;
  cbEvent.transactionHash = event.transaction.hash;
  cbEvent.save();
  
  let stats = getOrCreateStats();
  stats.circuitBreakerTriggers = stats.circuitBreakerTriggers.plus(BigInt.fromI32(1));
  stats.save();
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

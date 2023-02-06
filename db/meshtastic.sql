-- Adminer 4.8.1 MySQL 8.0.32-0ubuntu0.20.04.2 dump

SET NAMES utf8;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;

SET NAMES utf8mb4;

DROP TABLE IF EXISTS `meshNodes`;
CREATE TABLE `meshNodes` (
  `id` varchar(10) COLLATE utf8mb4_general_ci NOT NULL,
  `longName` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'UNDEF',
  `shortName` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'UNDEF',
  `hardware` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'UNDEF',
  `latitude` float DEFAULT '0',
  `longitude` float DEFAULT '0',
  `altitude` float DEFAULT '0',
  `batteryLevel` int DEFAULT NULL,
  `batteryVoltage` float DEFAULT NULL,
  `envVoltage` float DEFAULT NULL,
  `envCurrent` float DEFAULT NULL,
  `temperature` float DEFAULT NULL,
  `humidity` float DEFAULT NULL,
  `pressure` float DEFAULT NULL,
  `airUtil` float DEFAULT '0',
  `chUtil` float DEFAULT '0',
  `isRouter` int DEFAULT '0',
  `lastPacketID` bigint unsigned DEFAULT '0',
  `positionTimestamp` bigint unsigned DEFAULT '0',
  `timestamp` bigint unsigned DEFAULT '0',
  UNIQUE KEY `id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


DROP TABLE IF EXISTS `nodesPositionHistory`;
CREATE TABLE `nodesPositionHistory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `nodeID` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `latitude` float NOT NULL,
  `longitude` float NOT NULL,
  `timestamp` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


DROP TABLE IF EXISTS `packetIdHistory`;
CREATE TABLE `packetIdHistory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `nodeID` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `packetID` bigint DEFAULT NULL,
  `timestamp` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


DROP TABLE IF EXISTS `packetRates`;
CREATE TABLE `packetRates` (
  `id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `packetRate` bigint NOT NULL DEFAULT '0',
  `packetRateTS` json NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- 2023-02-06 10:51:24

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
  `batteryLevel` int DEFAULT '0',
  `batteryVoltage` int DEFAULT '0',
  `temperature` float DEFAULT '0',
  `humidity` float DEFAULT '0',
  `pressure` float DEFAULT '0',
  `airUtil` float DEFAULT '0',
  `chUtil` float DEFAULT '0',
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

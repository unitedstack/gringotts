LOCK TABLES `product` WRITE;
INSERT INTO `product` VALUES (1,'658e807b-5ae7-49a0-8941-2b89e832248d','instance:m1.tiny','compute','default','some decs','regular',0,0.4800,'hour',2,5.7600,'2014-02-06 09:52:16',NULL,NULL),(2,'535a8343-929c-499b-995c-d1ee6fe4172a','volume.size','block_storage','default','some decs','regular',0,0.0200,'hour',4,0.0000,'2014-02-06 09:52:25',NULL,NULL),(3,'cd3d5aec-f264-46c7-9ec5-9ee2061d232c','cirros-0.3.1-x86_64-uec:ce2293db-5337-4701-92b1-a82c814269d3','compute','default','some decs','regular',0,0.0300,'hour',0,0.0000,'2014-02-06 09:52:31',NULL,NULL),(4,'b387bf09-8673-4d6f-b236-6cc5243619cd','instance:m1.small','compute','default','some decs','regular',0,0.5100,'hour',0,0.0000,'2014-02-07 00:59:46',NULL,NULL),(5,'76d6d456-7b05-40be-a9af-50ea8c0e1b48','instance:m1.large','compute','default','some decs','regular',0,1.5400,'hour',0,0.0000,'2014-02-07 01:06:11',NULL,NULL);
UNLOCK TABLES;

LOCK TABLES `account` WRITE;
INSERT INTO `account` VALUES (1,'b5612eac64b548b28015e7e79847234d','b81bb5c426a8422cb74918059f6af09d',94.2400,5.7600,'CNY',NULL,'2014-02-13 10:45:21');
UNLOCK TABLES;

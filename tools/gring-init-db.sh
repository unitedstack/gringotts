QL_HOST=${MYSQL_HOST:-127.0.0.1}
MYSQL_USER=${MYSQL_USER:-gringotts}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-3c5b1edd1b9e1a4a33bf830c}
OPENRC=${OPENRC:-./openrc}
ADMIN_USER_PROJECT=${ADMIN_USER_PROJECT:-openstack}

# Add products
PRODUCT_SQL="USE gringotts; INSERT INTO product VALUES"

P_1="(1,'98f2ce8b-8ad3-42db-b82e-dd022381d1bc','volume.size','block_storage','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.0020\"]], \"base_price\": \"0\"}}',0, '2014-02-09 08:16:10',NULL,NULL),"
P_2="(2,'e1cd002a-bef5-4306-b60e-8e6f54b80548','snapshot.size','block_storage','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.0020\"]], \"base_price\": \"0\"}}',0,'2014-02-09 08:20:06',NULL,NULL),"
P_3="(3,'a7ee0483-ff48-4567-84c4-932801cacfad','ip.floating','network','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.0300\"]], \"base_price\": \"0\"}}',0,'2014-02-11 08:21:17',NULL,NULL),"
P_4="(4,'4038d1b8-e08f-4824-9f4e-f277d15c5bfe','router','network','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.0500\"]], \"base_price\": \"0\"}}',0,'2014-02-11 09:02:38',NULL,NULL),"
P_5="(5,'0ab4bc1b-938f-4b9e-bebd-7e91dd58c85d','instance:micro-1','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.0560\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:42:15',NULL,NULL),"
P_6="(6,'9425b452-d0fb-406c-ba1b-c00bec291a02','instance:micro-2','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.1110\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:42:59',NULL,NULL),"
P_7="(7,'33969e9b-27b3-4772-acbc-a094940493f0','instance:standard-1','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.2220\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:43:49',NULL,NULL),"
P_8="(8,'2cda8174-4b1d-4988-8d0f-e94b46442bce','instance:standard-2','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.4440\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:44:05',NULL,NULL),"
P_9="(9,'bea31dc8-4140-47ee-8b48-4983f0f28a0f','instance:standard-4','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.8890\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:44:22',NULL,NULL),"
P_10="(10,'da55dddc-aa4e-4439-ba30-8bcfba36094b','instance:standard-8','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"1.7780\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:44:46',NULL,NULL),"
P_11="(11,'049378d6-8918-45be-b023-00fd573267ff','instance:standard-12','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"3.5560\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:45:01',NULL,NULL),"
P_12="(12,'e73b7486-0071-4bf7-8ea2-dca040a8dee0','instance:memory-1','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.3610\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:45:41',NULL,NULL),"
P_13="(13,'72af128b-9e82-45e6-824d-b15fcb01fbd3','instance:memory-2','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.7220\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:46:02',NULL,NULL),"
P_14="(14,'46345fe6-ab66-4f39-b6ca-b2945557e999','instance:memory-4','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"1.4440\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:46:16',NULL,NULL),"
P_15="(15,'732a3fe2-2837-4e46-80cd-ae6579c99121','instance:memory-8','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"2.8890\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:46:37',NULL,NULL),"
P_16="(16,'41579554-6b2c-4cd9-965c-0f2544d68a24','instance:compute-2','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.3330\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:47:19',NULL,NULL),"
P_17="(17,'4d2f6900-8f75-4f8d-877d-dff4dec1a57b','instance:compute-4','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"0.6670\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:47:43',NULL,NULL),"
P_18="(18,'cef8cb7b-b0a5-46ff-80a5-57d82e7ac611','instance:compute-8','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"1.3330\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:47:58',NULL,NULL),"
P_19="(19,'b45234b1-64fd-4572-8e71-2d5ff3e62593','instance:compute-12','compute','RegionOne','some decs','{\"price\": {\"type\": \"segmented\", \"segmented\": [[0, \"2.6670\"]], \"base_price\": \"0\"}}',0,'2014-03-18 06:48:12',NULL,NULL);"

PRODUCT_SQL=$PRODUCT_SQL$P_1$P_2$P_3$P_4$P_5$P_6$P_7$P_8$P_9$P_10$P_11$P_12$P_13$P_14$P_15$P_16$P_17$P_18$P_19
mysql -h$MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASSWORD -e "$PRODUCT_SQL"

# Add admin account
source $OPENRC admin admin
ADMIN_USER_ID=$(openstack user list | awk "/ admin / {print \$2}")
ADMIN_TENANT_ID=$(openstack project list | awk "/ $ADMIN_USER_PROJECT / {print \$2}")
DOMAIN_ID=$(openstack project show $ADMIN_TENANT_ID | awk "/ domain_id / {print \$4}")
ACCOUNT_SQL="USE gringotts; INSERT INTO account VALUES(1, '$ADMIN_USER_ID', '$DOMAIN_ID', 10, 0, 0, 3, 0, 0, NULL, NULL, NULL);"
PROJECT_SQL="USE gringotts; INSERT INTO project VALUES(1, '$ADMIN_USER_ID', '$ADMIN_TENANT_ID', 0, '$DOMAIN_ID', NULL, NULL);"
USER_PROJECT_SQL="USE gringotts; INSERT INTO user_project VALUES(1, '$ADMIN_USER_ID', '$ADMIN_TENANT_ID', 0, '$DOMAIN_ID', NULL, NULL);"
mysql -h$MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASSWORD -e "$ACCOUNT_SQL"
mysql -h$MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASSWORD -e "$PROJECT_SQL"
mysql -h$MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASSWORD -e "$USER_PROJECT_SQL"

"""
Truncate the tables:
mysql> truncate `order`; truncate bill; truncate subscription; update product set quantity=0, total_price=0; update account set balance=100000, consumption=0;

Load test data to tables:
mysql> LOAD DATA INFILE '/tmp/load_bill.sql' INTO TABLE gringotts.bill; LOAD DATA INFILE '/tmp/load_order.sql' INTO TABLE gringotts.`order`; LOAD DATA INFILE '/tmp/load_subs.sql' INTO TABLE gringotts.subscription; LOAD DATA INFILE '/tmp/load_account.sql' INTO TABLE gringotts.account;
"""

import uuid
import random
import datetime

with open('/tmp/load_order.sql', 'w') as f1:
    now = datetime.datetime.utcnow() + datetime.timedelta(minutes=4)
    with open('/tmp/load_bill.sql', 'w') as f2:
        with open('/tmp/load_subs.sql', 'w') as f3:
            with open('/tmp/load_account.sql', 'w') as f4:
                for i in xrange(2500):
                    project_id = str(uuid.uuid4())
                    user_id = str(uuid.uuid4())
                    created_at = datetime.datetime.utcnow()
                    updated_at = datetime.datetime.utcnow()

                    sql_4 = "0\t%(user_id)s\t%(project_id)s\t9997.6\t2.4\tCNY\t" \
                            "%(created_at)s\t%(updated_at)s" % \
                            dict(user_id=user_id, project_id=project_id,
                                 created_at=created_at, updated_at=updated_at)
                    sql_4 += '\r\n'
                    f4.write(sql_4)

                    for i in xrange(40):
                        order_id=str(uuid.uuid4())
                        resource_id=str(uuid.uuid4())
                        cron_time = now + datetime.timedelta(seconds=random.randint(0, 3600))
                        date_time = datetime.datetime.utcnow()
                        created_at = datetime.datetime.utcnow()
                        updated_at = datetime.datetime.utcnow()

                        sql_1 = "0\t%(order_id)s\t%(resource_id)s\tresource-name\t" \
                                "instance\trunning\t0.06\thour\t0.06\t%(cron_time)s\t" \
                                "%(date_time)s\t%(user_id)s\t%(project_id)s\t" \
                                "%(created_at)s\t%(updated_at)s" % \
                                dict(order_id=order_id, resource_id=resource_id, cron_time=cron_time, date_time=date_time,
                                     user_id=user_id, project_id=project_id, created_at=created_at, updated_at=updated_at)
                        sql_1 += '\r\n'

                        bill_id = str(uuid.uuid4())
                        start_time = cron_time - datetime.timedelta(hours=1)
                        end_time = cron_time
                        sql_2 = "0\t%(bill_id)s\t%(start_time)s\t%(end_time)s\t" \
                                "instance\tpayed\t0.06\thour\t0.06\t%(order_id)s\t" \
                                "%(resource_id)s\tremarks\t%(user_id)s\t%(project_id)s\t"\
                                "%(created_at)s\t%(updated_at)s" % \
                                dict(bill_id=bill_id, start_time=start_time, end_time=end_time,
                                     order_id=order_id, resource_id=resource_id, user_id=user_id,
                                     project_id=project_id, created_at=created_at, updated_at=updated_at)

                        sql_2 += '\r\n'

                        sub_id = str(uuid.uuid4())
                        product_id = '658e807b-5ae7-49a0-8941-2b89e832248f'
                        sql_3 = "0\t%(sub_id)s\trunning\t%(product_id)s\t0.06\thour\t1\t0.06\t" \
                                "%(order_id)s\t%(user_id)s\t%(project_id)s\t%(created_at)s\t%(updated_at)s" % \
                                dict(sub_id=sub_id, product_id=product_id, order_id=order_id,
                                     user_id=user_id, project_id=project_id, created_at=created_at,
                                     updated_at=updated_at)

                        sql_3 += '\r\n'

                        f1.write(sql_1)
                        f2.write(sql_2)
                        f3.write(sql_3)

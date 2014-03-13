import uuid
import random
import datetime

with open('/tmp/load_order.sql', 'w') as f1:
    now = datetime.datetime.utcnow() + datetime.timedelta(minutes=0.5)
    with open('/tmp/load_bill.sql', 'w') as f2:
        for i in xrange(3600):
            order_id=str(uuid.uuid4())
            resource_id=str(uuid.uuid4())
            user_id = '23358319a6ec4d1aa12f6c97303ec5b0'
            project_id='1e2efba0241549a08d2426f0a26b8416'
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

            f1.write(sql_1)
            f2.write(sql_2)

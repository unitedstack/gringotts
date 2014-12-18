import commands
from decimal import Decimal, ROUND_HALF_UP


def to_decimal(value):
    return Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def is_zero(value):
    if value == '0.0000' or value == 'NULL':
        return True
    return False


projects = commands.getoutput("mysql -e \"select project_id from gringotts.project\"").split("\n")[1:]


for project in projects:
    project_consumption = commands.getoutput("mysql -e 'select consumption from gringotts.project where project_id=\"%s\"'" % project).split("\n")[1]
    orders_consumption = commands.getoutput("mysql -e 'select sum(total_price) from gringotts.order where project_id=\"%s\"'" % project).split("\n")[1]
    if is_zero(project_consumption) or is_zero(orders_consumption):
        continue
    if project_consumption != orders_consumption:
        order_in_orders = commands.getoutput("mysql -e 'select order_id from gringotts.order where project_id=\"%s\"'" % project).split("\n")[1:]
        order_in_bills = commands.getoutput("mysql -e 'select distinct(order_id) from gringotts.bill where project_id=\"%s\"'" % project).split("\n")[1:]
        diff = set(order_in_bills) - set(order_in_orders)
        bad_orders = []
        if not diff:
            for order in order_in_orders:
                order_total_price = commands.getoutput("mysql -e 'select total_price from gringotts.order where order_id=\"%s\"'" % order).split("\n")[1]
                bill_total_price = commands.getoutput("mysql -e 'select sum(total_price) from gringotts.bill where order_id=\"%s\"'" % order).split("\n")[1]
                if is_zero(order_total_price) or is_zero(bill_total_price):
                    continue
                if order_total_price != bill_total_price:
                    bad_orders.append(order)
        else:
            for order in diff:
                bill_total_price = commands.getoutput("mysql -e 'select sum(total_price) from gringotts.bill where order_id=\"%s\"'" % order).split("\n")[1]
                commands.getoutput("mysql -e 'update gringotts.project set consumption=consumption-%s where project_id=\"%s\"'" % (bill_total_price, project))
                commands.getoutput("mysql -e 'update gringotts.user_project set consumption=consumption-%s where project_id=\"%s\"'" % (bill_total_price, project))
                user_id = commands.getoutput("mysql -e 'select user_id from gringotts.project where project_id=\"%s\"'" % project).split("\n")[1]
                commands.getoutput("mysql -e 'update gringotts.account set consumption=consumption-%s, balance=balance+%s where user_id=\"%s\"'" % (bill_total_price, bill_total_price, user_id))
                commands.getoutput("mysql -e 'delete from gringotts.bill where order_id=\"%s\"'" % order)

        print project, project_consumption, orders_consumption, diff, bad_orderumption

"""Model classes for use in the storage API.
This model is the abstraction layer across all DB models.
"""


class Model(object):
    """Base class for storage API models.
    """

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in kwds.iteritems():
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Model):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], Model):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()


class Product(Model):
    """The DB Model for Product, which should has the same fields
    with API models.
    """

    def __init__(self,
                 uuid, name, description,
                 meter_name, source,
                 region_id, user_id, project_id,
                 type, time_size, time_unit,
                 quantity_from, quantity_to, quantity_unit,
                 price,currency,
                 created_at, updated_at):
        Model.__init__(
            self,
            uuid=uuid,
            name=name,
            description=description,
            meter_name=meter_name,
            source=source,
            region_id=region_id,
            user_id=user_id,
            project_id=project_id,
            type=type,
            time_size=time_size,
            time_unit=time_unit,
            quantity_from=quantity_from,
            quantity_to=quantity_to,
            quantity_unit=quantity_unit,
            price=price,
            currency=currency,
            created_at=created_at,
            updated_at=updated_at)

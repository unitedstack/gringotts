"""update bill table use partition

Revision ID: 1d22a66f81f0
Revises: 25fa0c3b7e89
Create Date: 2016-12-19 15:08:48.959430

"""

# revision identifiers, used by Alembic.
revision = '1d22a66f81f0'
down_revision = '25fa0c3b7e89'

from alembic import op


def upgrade():
    op.execute("alter table bill modify id int NOT NULL;")
    op.execute("alter table bill drop primary key;")
    op.execute("alter table bill add primary key(id, start_time);")
    op.execute("alter table bill partition by RANGE(YEAR(start_time)) \
               subpartition by hash(MONTH(start_time)) \
               (partition p_2015 values less than (2016), \
               partition p_2016 values less than (2017), \
               partition p_2017 values less than (2018), \
               partition p_2018 values less than (2019), \
               partition p_2019 values less than (2020), \
               partition p_2020 values less than (2021), \
               partition p_2021 values less than (2022), \
               partition p_2022 values less than (2023), \
               partition p_2023 values less than (2024), \
               partition p_2024 values less than (2025), \
               partition p_2025 values less than MAXVALUE)")


def downgrade():
    pass

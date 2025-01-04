create table accounts
(
    id               integer primary key,
    type             integer,
    currency_id      integer,
    name             text,
    starting_balance real,
    balance          real,
    credit_limit     real,
    goal             real,
    is_in_balance    boolean,
    is_in_expenses   boolean,
    show_order       integer,
    icon_id          integer,
    color            integer,
    is_archived      boolean
);

create table categories
(
    id                 integer primary key,
    type               integer,
    name               text,
    icon_id            integer,
    color              integer,
    parent_category_id integer
);

create table currencies
(
    id         integer primary key,
    name_short text,
    symbol     text,
    is_default boolean
);

create table transactions
(
    id                 integer primary key,
    type               integer,
    timestamp          integer,
    currency_id        integer,
    account_id         integer,
    destination_id     integer,
    amount             real,
    destination_amount real,
    exchange_rate      real,
    comment            text,
    is_scheduled       boolean
);


create table balance_history
(
    id             integer primary key,
    account_id     integer,
    transaction_id integer,
    timestamp      integer,
    balance        real
);


insert into currencies (id, name_short, symbol, is_default)
values (10002, 'EUR', '€', 0),
       (10051, 'USD', '$', 0),
       (10057, 'UAH', '₴', 1);

insert into accounts (id, type, currency_id, name, starting_balance, credit_limit, goal, is_in_balance,
                      is_in_expenses, show_order, icon_id, color, is_archived)
select _id, _ty, _c_i, _na, cast(_a_m_b as real), _a_m_l, _a_m_g, _a_i_i_b,
       _a_i_i_e, _a_o, _ic, 16777216 + _co, _ar
from de
where _a_i_i_e is not null and _b_i = (select max(_id) from ba);

insert into categories (id, type, name, icon_id, color, parent_category_id)
select  _id, _ty, _na, _ic, 16777216 + _co, _pi
from de
where _a_i_i_e is null and _b_i = (select max(_id) from ba);

insert into transactions (id, type, timestamp, currency_id, account_id, destination_id, amount,
                          destination_amount, exchange_rate, comment, is_scheduled)
select _id, _ty, _da / 1000, _cr_i, _a_i, _d_i, _a_m,
       _d_m, _c_f, _co, _sch
from tr
where _b_i = (select max(_id) from ba);

alter table transactions
    add column curr_amount real;

update transactions
set type = 2
where account_id in (select id from accounts) and destination_id in (select id from accounts);

update transactions
set curr_amount = round(destination_amount * transactions.exchange_rate, 2)
where exchange_rate < 1 and type = 0;

update transactions
set destination_amount = curr_amount
where curr_amount is not null;

update transactions
set exchange_rate = destination_amount / amount
where exchange_rate < 1 and type = 0;

alter table transactions
drop column curr_amount;

update accounts
set balance =
    round(ifnull(accounts.starting_balance, 0)
        + (select ifnull(sum(destination_amount), 0) as transfers_to
           from transactions where destination_id = accounts.id and is_scheduled = 0)
        + (select ifnull(sum(amount), 0) as incomes
           from transactions where account_id = accounts.id and type = 1 and is_scheduled = 0)
        - (select ifnull(sum(amount), 0)
            as expenses from transactions where account_id = accounts.id and type = 0 and is_scheduled = 0)
        - (select ifnull(sum(amount), 0)
            as transfers_from from transactions where account_id = accounts.id and type = 2 and is_scheduled = 0),
    2);

pragma user_version = 99;
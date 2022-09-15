# OrderBot
Matrix bot for take-out/delivery balance tracking


## Installation (using Docker)

1. Clone this repository
2. Fill in `matrix.env`
```
DBPATH=
MUSERNAME=
MSERVER=
MPASSWORD=
```
3. Start container with `docker-compose up -d`

## Usage

Invite the bot into a room (it will auto-join). Start commands with `!ob`. 
Using `--help` or `-h` displays the help message for the used command.

### user commands

```
    join                join system
    register            register a different user
    payout              pay out the remaining debt/due balance
    init                add initial balance
    balance             display the balance of all users
    suggest             return the last 5 orders, with pricing
```

### order commands

```
    start               start a new collective order
    add                 add new order to collective order
    tip                 add a tip
    remove              remove order from collective order
    end                 finish collective order
    cancel              cancel current collective order
    print               display current collective order
```

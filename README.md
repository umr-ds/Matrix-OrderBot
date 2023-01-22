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
Using `--help` or `-h` displays the help message for any command.

### Commands

Overall, the commands are split into two categories:
- `user` commands: These commands are used to manage the users' accounts.
- `order` commands: These commands are used to order.

### User commands

```
    join                join system with matrix-address
    register            register a different user, e.g. via just the name, use join to register yourself
    transfer            transfer money from one user to another
    payout              get a suggestion for a potential payout
    balance             display the balance of all users
    init                initialize a user's balance
    exit                deactivates user, if balance is zero
```

### Order commands

```
    start               start a new collective order
    add                 add item of a user to order
    tip                 set tip of the order
    remove              remove a user's item from the current collective order, all items of a user or all users
    edit                edit the price of an item
    end                 finish collective order
    cancel              cancel current collective order
    print               display current collective order
    reopen              reopen last order, if no current order
    suggest             return the last 5 ordered item of the user, with
                        pricing
    reorder             reorder the last item of a user, from the last order
    history             display history of the last [k] orders
```

### Examples

Here, you can find a short set of commands which demonstrates the usage of the bot.

`!ob user join --all`  
registers all users in the matrix room with their current display name and their matrix address  


`!ob order start "The Foo Bar"`  
starts a new collective order with the name "The Foo Bar"  
`!ob order add "Pizza" 10.50`  
adds an item with name "Pizza" and price of 10.50 to the collective order for the current user   
`!ob order add "Burger" --name @user:foo.bar 20`  
adds an item with name "Burger" and price 20.00 to the collective order for user @user:foo.bar, assuming that user is registered  
`!ob order tip 5`  
adds a tip of 5.00 to the collective order  
`!ob order end`  
ends the current collective order, assuming that the current user paid 

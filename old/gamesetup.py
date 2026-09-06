import random 
WIDTH = 8
HEIGHT = 6
def make_world():
    world = []
    for row in range(HEIGHT):
        new_row = []
        for col in range(WIDTH):
            title = random.choices(['.', 'T', 'R', '~'], weights=[70, 15, 10, 5])[0]
            new_row.append(title)
        world.append(new_row)
        world[0][0] = "."
    return world

def print_world(world,player_row,player_col):
    print()
    for row in range(HEIGHT):
        line = ""
        for col in range(WIDTH):
            if row == player_row and col == player_col:
                line += "@"
            else:
                line += world[row][col] + " "
        print(line)
    print()

def print_inventory(inventory):
    print(f"Inventory -> Wood: {inventory['wood']} Stone: {inventory['stone']}")

def main():
    world = make_world()
    player_row , player_col = 0, 0
    facing_row , facing_col = 0, 1
    inventory = {'wood': 0, 'stone': 0}

    print("--~WELCOME TO SUNDERED REALM~--")
    print("To move press w to go up s to go down a to go left and d to go right")
    print("Walk into a tree --> T to chop wood, a rock --> R to mine stone")
    print("To place blocks press p ")
    print("Exit --> q ")
    print("@ = you, the wandering traveller")
    print("T = tree      R = rock/stone      . = open ground")
    print("~ = water (impassable)      # = a block you've placed")
    print()

    while True:
        print_world(world, player_row, player_col)
        print_inventory(inventory)
        command = input("What shall you desire?").lower().strip()
#All the keys are programmed here
        if command == "q":
            print("Farewell, traveller. May your journey be fruitful.")
            break
        new_row , new_col = player_row, player_col
        if command == "w":
            new_row -= 1
            facing_row, facing_col = -1, 0
        elif command == "s":
            new_row += 1
            facing_row, facing_col = 1, 0
        elif command == "a":
            new_col -= 1
            facing_row, facing_col = 0, -1
        elif command == "d":
            new_col += 1
            facing_row, facing_col = 0, 1
        elif command == "p":
            place_row = player_row + facing_row
            place_col = player_col + facing_col
            if 0 <= place_row < HEIGHT and 0 <= place_col < WIDTH:
                if inventory['wood'] > 0 and world[place_row][place_col] == '.':
                    world[place_row][place_col] = '#'
                    inventory['wood'] -= 1
                    print("You have placed a block")
                else:
                    print("Either you have no wood or this space is occupied.")
            continue
        else:
            print("Your otherwordly knowledge is not recognised.")

        if not (0 <= new_row <HEIGHT and 0 <= new_col < WIDTH):
            print("The infinity beyond contains nothingness.")
            continue
        target = world[new_row][new_col]

        if target == '~':
            print("Helpfull spirit : Splash! The watery depths are dangerous. I advise you not to go")
        elif target == 'T':
            inventory['wood'] += 1
            world[new_row][new_col] = '.'
            print("Obtained 1 wood")
        elif target == 'R':
            inventory['stone'] += 1
            world[new_row][new_col] = '.'
            print("Obtained 1 stone")
        else:
            player_row, player_col = new_row, new_col

if __name__ == "__main__":
    main()
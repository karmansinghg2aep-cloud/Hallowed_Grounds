# SUNDERED REALM --> Pygame edition

import pygame


# --~SETUP~--
pygame.init()

window_width = 640
window_height = 480
screen = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("Sundered Realm")

# Adding the colors
background_color = (20, 20, 20) # dark blue
player_color = (240, 220, 80) # gold 

# The player is a square here. We'll track the x and y position.
player_x = window_width // 2 # x position of the player
player_y = window_height // 2 # y position of the player
player_size = 30  # size of the player
player_speed = 5 # pixels per frame

clock = pygame.time.Clock()

# ---<Game Loop>---
running = True
while running:
    # Handle events (things that happen once)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Checks which keys are held down
    keys = pygame.key.get_pressed()
    if keys[pygame.K_w]:  # Move up
        player_y -= player_speed
    if keys[pygame.K_s]:  # Move down
        player_y += player_speed
    if keys[pygame.K_a]:  # Move left
        player_x -= player_speed
    if keys[pygame.K_d]:  # Move right
        player_x += player_speed

    # Keeps player confined 
    player_x = max(0, min(player_x, window_width - player_size))
    player_y = max(0, min(player_y, window_height - player_size))

    # Print everything to the screen
    screen.fill(background_color)  # Fill the background
    pygame.draw.rect(screen, player_color, (player_x, player_y, player_size, player_size))
    pygame.display.flip()  # Update the display

    # Run at 60fps
    clock.tick(60)

pygame.quit()

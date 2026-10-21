execute unless entity @s[type=minecraft:player] run return 0
execute unless dimension minecraft:overworld unless dimension minecampus_mensa:study run return run tellraw @s {"text":"Visit the Mensa from the campus Overworld, so your return point can be saved.","color":"yellow"}
execute unless dimension minecampus_mensa:study run function minecampus_mensa:capture
execute unless score #built mc_mensa matches 1 run function minecampus_mensa:prepare
execute in minecampus_mensa:study run tp @s 49 64 94 180 0
tellraw @s {"text":"Mensa architectural study: footprint and layout references, approximate interiors. The campus scan is untouched.","color":"aqua"}
tellraw @s [{"text":"Walk through the entrance, then take the stairs on the right to the dining hall. ","color":"white"},{"text":"Return to campus","color":"green","underlined":true,"clickEvent":{"action":"run_command","value":"/function minecampus_mensa:back"}}]

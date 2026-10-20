tag @s add minecampus_started
tellraw @s [{"text":"Minecampus · TUM Garching","color":"aqua","bold":true}]
tellraw @s [{"text":"Actual Minecraft Java. Press E for inventory/crafting and F5 for third person. ","color":"white"},{"text":"Campus help","color":"green","underlined":true,"clickEvent":{"action":"run_command","value":"/function minecampus:help"}}]
function minecampus:kit

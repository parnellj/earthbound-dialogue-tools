import os
from pprint import pprint
import yaml
import flatdict
import pandas
import re
from collections import OrderedDict
import csv

CD = os.path.dirname(os.path.realpath(__file__))
decompilation_path = os.path.join(CD, 'decompilations', '20230106_decompilation')


class GameData:
    def __init__(self, target_decompilation):
        self.target_decompilation = target_decompilation
        self.npcs = {}
        self.map_sprites = {}
        self.raw_script = ''

        with open(os.path.join(self.target_decompilation, 'npc_config_table.yml')) as f:
            self.npcs = yaml.safe_load(f)

        with open(os.path.join(self.target_decompilation, 'map_sprites.yml')) as f:
            self.map_sprites = yaml.safe_load(f)

        with open(os.path.join(self.target_decompilation, "_cleanscript", "b.txt")) as f:
            self.raw_script = f.read()

        self.indexed_script = self.parse_raw_script()
        self.append_npc_locations()
        self.append_npc_dialog()
        self.dereference_all_dialog()
        self.label_sprites()

    def parse_raw_script(self):
        script_groups = re.findall(r'\; \$([0-9,A-F]{6})(.+?)(?=\; \$[0-9,A-F]{6})',
                                   self.raw_script,
                                   re.M | re.DOTALL)
        indexed_script = {idx: [line for line in content.split('\n') if line] for idx, content in script_groups}
        return indexed_script

    def append_npc_locations(self):
        for y_sector_number, x_sectors in self.map_sprites.items():
            for x_sector_number, sprites in x_sectors.items():
                if sprites:
                    for sprite in sprites:
                        self.npcs[sprite['NPC ID']].update(
                            x_pixel_abs=x_sector_number * 256 + sprite['X'],
                            y_pixel_abs=y_sector_number * 256 + sprite['Y'],
                            x_tile=(x_sector_number * 8),
                            y_tile=(y_sector_number * 8),
                            x_sector=x_sector_number,
                            y_sector=y_sector_number,
                            x_sector_offset=sprite['X'],
                            y_sector_offset=sprite['Y']
                        )
        return

    def append_npc_dialog(self):
        for npc_id, npc in self.npcs.items():
            dialog_1_pointer_raw = npc['Text Pointer 1']
            dialog_2_pointer_raw = npc['Text Pointer 2']
            dialog_1_pointer_hex = re.search(r'0x([0-9a-f]{6})', dialog_1_pointer_raw)
            dialog_2_pointer_hex = re.search(r'0x([0-9a-f]{6})', dialog_2_pointer_raw)
            dialog_1_pointer = dialog_1_pointer_hex.group(1).upper() if dialog_1_pointer_hex else None
            dialog_2_pointer = dialog_2_pointer_hex.group(1).upper() if dialog_2_pointer_hex else None

            npc.update(
                dialog_1_pointer=dialog_1_pointer,
                dialog_2_pointer=dialog_2_pointer,
                dialog_1=self.indexed_script[dialog_1_pointer] if dialog_1_pointer else None,
                dialog_2=self.indexed_script[dialog_2_pointer] if dialog_2_pointer else None
            )

    def label_sprites(self):
        with open(os.path.join(CD, 'sprite_groups.csv')) as f:
            reader = csv.reader(f)
            next(reader) # pop header row
            sprite_groups = {int(rows[0]): rows[1] for rows in reader}

        for npc_id, npc in self.npcs.items():
            npc['sprite_label'] = sprite_groups[npc['Sprite']]

        return

    def dereference_all_dialog(self):
        for npc_id, npc in self.npcs.items():
            if npc['dialog_1']:
                dereferenced_dialog = self.dereference_dialog(npc['dialog_1'])
                npc['dialog_1_dereferenced'] = dereferenced_dialog
        return

    def dereference_dialog(self, dialog, depth=0, max_depth=10):
        dereferenced_dialog = OrderedDict()
        if depth >= max_depth or not dialog:
            return dereferenced_dialog

        for line in dialog:
            dialog_references = re.findall(r'L_([0-9A-F]{6})', line)

            if re.match(r'^L_[0-9A-F]{6}:$', line) or re.match(r'^Npc[0-9]{4}:$', line) or not dialog_references:
                dereferenced_dialog[line] = None
                continue

            for index in dialog_references:
                target_dialog = self.indexed_script[index] if index in self.indexed_script else OrderedDict()
                dereferenced_dialog["{}:{}".format(line, index)] = self.dereference_dialog(target_dialog, depth + 1)
        return dereferenced_dialog


if __name__ == '__main__':
    gd = GameData(decompilation_path)

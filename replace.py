# import os

# project_path = "STREIX"

# for root, dirs, files in os.walk(project_path):
#     for file in files:
#         if file.endswith(".py"):
#             file_path = os.path.join(root, file)
#             with open(file_path, "r", encoding="utf-8") as f:
#                 code = f.read()

#             new_code = code.replace("datetime.utcnow()", "datetime.now(timezone.utc)")
#             code = code.replace("datetime.datetime.utcnow()", "datetime.datetime.now(datetime.timezone.utc)")


#             if new_code != code:
#                 with open(file_path, "w", encoding="utf-8") as f:
#                     f.write(new_code)


# print("all datetime,now calls in streix replaced!")
from itertools import permutations
import string
letters = list(string.ascii_letters)
numbers = list(range(10))
values = letters+numbers
comb = permutations(values, 8)
codes = list(comb)
print(''.join(codes[87]), len(codes))

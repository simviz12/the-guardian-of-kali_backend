from PIL import Image

img = Image.open(r'C:\Users\usuario\.gemini\antigravity\brain\96b9640d-b478-4fdf-b978-90176f7f0ee0\kaliche_logo_1790608933116.jpg').convert('RGBA')
datas = img.getdata()

newData = []
for item in datas:
    if item[0] > 240 and item[1] > 240 and item[2] > 240:
        newData.append((255, 255, 255, 0))
    else:
        newData.append(item)

img.putdata(newData)
img.save(r'C:\Users\usuario\Desktop\tarea_imposible\kaliche.png', 'PNG')
img.save(r'C:\Users\usuario\Desktop\tarea_imposible\kaliche.ico', format='ICO', sizes=[(256, 256)])
print('Done')


class Colors:

    def __init__(self):
        pass

    @staticmethod
    def to_rgb_hex(color_candidate):
        if '0x' in color_candidate:
            return hex(int(color_candidate, base=16))
        elif '#' in color_candidate:
            return hex(int(color_candidate.replace('#', '0x'), base=16))
        else:
            return next((color[1] for color in COLORS if color_candidate.lower() in color[0]), None)


COLORS = [(['floralwhite', 'bloemenwit'], 0xfffaf0), (['koraal', 'coral'], 0xff7f50), (['distel', 'thistle'], 0xd8bfd8),
          (['gold', 'goud'], 0xffd700), (['hemelsblauw', 'skyblue'], 0x87ceff), (['firebrick', 'steenrood'], 0xb22222),
          (['donkerorgidee', 'darkorchid'], 0x9932cc), (['yellow', 'geel'], 0xffff00),
          (['darkolivegreen', 'donkerolijfgroen'], 0x556b2f), (['zand', 'tan'], 0xd2b48c), (['roze', 'pink'], 0xffc0cb),
          (['slategrey', 'leigrijs'], 0x708090), (['korenbloemblauw', 'cornflowerblue'], 0x6495ed),
          (['zwart', 'black'], 0x000000), (['azuur', 'azure'], 0xf0ffff), (['donkercyaan', 'darkcyan'], 0x8b8b),
          (['bisquei', 'bisque'], 0xffe4c4), (['honingdauw', 'honeydew'], 0xf0fff0),
          (['greenyellow', 'groengeel'], 0xadff2f), (['navajowit', 'navajowhite'], 0xffdead),
          (['mediumorchid', 'midenorgidee'], 0xba55d3), (['plum', 'pruim'], 0xdda0dd),
          (['faalturkoois', 'paleturquoise'], 0xafeeee), (['bosgroen', 'forestgreen'], 0x228b22),
          (['geestwit', 'ghostwhite'], 0xf8f8ff), (['chartreuse'], 0x7fff00), (['zeegroen', 'seagreen'], 0x2e8b52),
          (['springgreen', 'lentegroen'], 0xff7f), (['donkerviolet', 'darkviolet'], 0x9400d3),
          (['lightsalmon', 'lichtzalm'], 0xffa07a), (['dieproze', 'deeppink'], 0xff1493),
          (['warmroze', 'hotpink'], 0xff69b4), (['turquoise'], 0x40e0d0), (['indianred', 'indischrood'], 0xcd5c5c),
          (['darkgrey', 'donkergrijs'], 0xa9a9a9), (['groen', 'green'], 0xff00),
          (['guldenroede', 'goldenrod'], 0xdaa520), (['kaki', 'khaki'], 0xfff68f),
          (['lichtguldenroedegeel', 'ltgoldenrodyello'], 0xfafad2), (['oudroze', 'rosybrown'], 0xbc8f8f),
          (['lightseagreen', 'lichtzeegroen'], 0x20b2aa), (['cyan', 'cyaan'], 0xffff),
          (['lichtgrijs', 'lightgray'], 0xd3d3d3), (['kastanjebruin', 'maroon'], 0xb03060),
          (['darkturquoise', 'donkerturquoise'], 0xced1), (['darkgreen', 'donkergroen'], 0x6400),
          (['antiekwit', 'antiquewhite'], 0xfaebd7), (['blauwpaars', 'blueviolet'], 0x8a2be2),
          (['lichtcyaan', 'lightcyan'], 0xe0ffff), (['moccasin'], 0xffe4b5),
          (['darkseagreen', 'donkerzeegroen'], 0x8fbc8f), (['lightpink', 'lichtroze'], 0xffb6c1),
          (['middenroodviolet', 'mediumvioletred'], 0xc71585), (['zachtroze', 'mistyrose'], 0xffe4e1),
          (['diephemelsblauw', 'deepskyblue'], 0xbfff), (['lightcoral', 'lichtkoraal'], 0xf08080),
          (['orchidee', 'orchid'], 0xda70d6), (['rookwit', 'whitesmoke'], 0xf5f5f5),
          (['darkblue', 'donkerblauw'], 0x00008b), (['gebleekteamandel', 'blanchedalmond'], 0xffebcd),
          (['saddlebrown', 'zadelbruin'], 0x8b4513), (['donkeroranje', 'darkorange'], 0xff8c00),
          (['muntcreme', 'mintcream'], 0xf5fffa), (['donkermagenta', 'darkmagenta'], 0x8b008b),
          (['lavender', 'lavendel'], 0xe6e6fa), (['yellowgreen', 'geelgroen'], 0x9acd32), (['violet'], 0xee82ee),
          (['kant', 'oldlace'], 0xfdf5e6), (['lightskyblue', 'lichthemelsblauw'], 0x87cefa),
          (['dimgrey', 'matgrijs'], 0x696969), (['olivegreen', 'olijfgroen'], 0xcaff70),
          (['donkerzalm', 'darksalmon'], 0xe9967a), (['middenlentegroen', 'medspringgreen'], 0xfa9a),
          (['dark red', 'donkerrood'], 0x8b0000), (['darkkhaki', 'donkerkaki'], 0xbdb76b),
          (['middenaquamarijn', 'mediumaquamarine'], 0x66cdaa), (['oker', 'beige'], 0xf5f5dc),
          (['mediumpurple', 'middenpaars'], 0x9370db), (['cornsilk', 'maiszijde'], 0xfff8dc),
          (['red', 'rood'], 0xff0000), (['burlywood', 'hardhout'], 0xdeb887), (['wheat', 'tarwe'], 0xf5deb3),
          (['lightslateblue', 'lichtleiblauw'], 0x8470ff), (['lichtblauw', 'lightblue'], 0xadd8e6),
          (['steelblue', 'staalblauw'], 0x4682b4), (['lichtgeel', 'lightyellow'], 0xffffe0),
          (['middenturquoise', 'mediumturquoise'], 0x48d1cc), (['linen', 'linnen'], 0xfaf0e6),
          (['paars', 'purple'], 0xa020f0), (['donkerleigrijs', 'darkslategray'], 0x2f4f4f),
          (['terracotta', 'peru'], 0xcd852f), (['blauw', 'blue'], 0xff), (['grijs', 'grey'], 0xbebebe),
          (['ivoor', 'ivory'], 0xfffff0), (['bruin', 'brown'], 0xa52a2a), (['tomaat', 'tomato'], 0xff6347),
          (['oranjerood', 'orangered'], 0xff4500), (['lightsteelblue', 'lichtstaalblauw'], 0xb0c4de),
          (['middenzeegroen', 'mediumseagreen'], 0x3cb371), (['leiblauw', 'slateblue'], 0x6a5acd),
          (['lightgoldenrod', 'lichtguldenroede'], 0xeedd82), (['gainsboro', 'zachtgrijs'], 0xdcdcdc),
          (['lichtleigrijs', 'lightslategray'], 0x778899), (['marineblauw', 'navyblue'], 0x80),
          (['olivedrab', 'legergroen'], 0x6b8e23), (['sienna'], 0xa0522d), (['faalgroen', 'palegreen'], 0x98fb98),
          (['wit', 'white'], 0xffffff), (['donkerleiblauw', 'darkslateblue'], 0x483d8b),
          (['middenleiblauw', 'mediumslateblue'], 0x7b68ee), (['lavendelblos', 'lavenderblush'], 0xfff0f5),
          (['aquamarijn', 'aquamarine'], 0x7fffd4), (['violetred', 'roodviolet'], 0xd02090),
          (['faalguldenroede', 'palegoldenrod'], 0xeee8aa), (['seashell', 'schelp'], 0xfff5ee),
          (['zalm', 'salmon'], 0xfa8072), (['nachtblauw', 'midnightblue'], 0x191970),
          (['royalblue', 'koningsblauw'], 0x4169e1), (['faalroodpaars', 'palevioletred'], 0xdb7093),
          (['tan1', 'geelbruin'], 0xffa54f), (['chocolade', 'chocolate'], 0xd2691e),
          (['dodgerblue', 'poederblauw'], 0x1e90ff), (['aliceblue', 'aliceblauw'], 0xf0f8ff),
          (['lawngreen', 'grasgroen'], 0x7cfc00), (['lightgreen', 'lichtgroen'], 0x90ee90),
          (['orange', 'oranje'], 0xffa500), (['ijsblauw', 'cadetblue'], 0x5f9ea0),
          (['limegreen', 'limegroen'], 0x32cd32), (['sneeuw', 'snow'], 0xfffafa),
          (['zandbruin', 'sandybrown'], 0xf4a460), (['darkgoldenrod', 'donkerguldenroede'], 0xb8860b),
          (['magenta'], 0xff00ff), (['lemon', 'citroen'], 0xfffacd), (['mediumblue', 'middenblauw'], 0xcd)]

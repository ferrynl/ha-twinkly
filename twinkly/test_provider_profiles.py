import unittest
from modules.profiles import hue_profile,hue_profiles,govee_profile

class ProfileTests(unittest.TestCase):
    def test_hue_color(self):
        p=hue_profile({"id":"a","color":{},"dimming":{},"on":{"on":True}})
        self.assertTrue(p["capabilities"]["rgb"])
        self.assertTrue(p["state"]["on"])
    def test_white_only(self):
        self.assertFalse(hue_profile({"id":"a","on":{}})["capabilities"]["rgb"])
    def test_temperature(self):
        p=hue_profile({"id":"a","color_temperature":{"mirek_schema":{"mirek_minimum":153,"mirek_maximum":500}}})
        self.assertEqual(p["temperature_mirek"],{"min":153,"max":500})
    def test_join(self):
        p=hue_profiles([{"id":"a","owner":{"rid":"d"}}],[{"id":"d","product_data":{"model_id":"LCT","software_version":"1"}}])[0]
        self.assertEqual((p["model"],p["firmware"]),("LCT","1"))
    def test_hue_reachability_belongs_to_the_light_owner(self):
        lights = [{"id": name, "owner": {"rid": name}} for name in ("a", "b", "c")]
        profiles = hue_profiles(lights, [], [
            {"owner": {"rid": "a"}, "status": "connectivity_issue"},
            {"owner": {"rid": "b"}, "status": "connected"},
        ])
        self.assertEqual([profile["status"] for profile in profiles],
                         ["unavailable", "online", "unknown"])

    def test_mirek_is_current_only_in_white_mode(self):
        temperature = {"mirek_schema": {"mirek_minimum": 153, "mirek_maximum": 500},
                       "mirek": 370, "mirek_valid": False}
        light = {"id": "a", "color_temperature": temperature}
        self.assertIsNone(hue_profile(light)["state"]["mirek"])
        temperature["mirek_valid"] = True
        self.assertEqual(hue_profile(light)["state"]["mirek"], 370)

    def test_effects(self):
        self.assertEqual(hue_profile({"id":"a","effects":{"effect_values":["fire","fire",1]}})["capabilities"]["effects"],["fire"])
    def test_govee_unknown(self):
        p=govee_profile({"device":"a","sku":"H1234"})
        self.assertFalse(any(p["capabilities"].values()))
    def test_govee_status(self):
        p=govee_profile({"device":"a","sku":"H1234"},{"onOff":1,"brightness":50,"color":{"r":255,"g":0,"b":0},"colorTemInKelvin":3000})
        self.assertTrue(p["capabilities"]["rgb"])
        self.assertTrue(p["capabilities"]["temperature"])
        self.assertFalse(p["capabilities"]["segments"])
    def test_govee_invalid(self):
        p=govee_profile({"device":"a","sku":"H1234"},{"onOff":True,"brightness":101,"color":{"r":256,"g":0,"b":0}})
        self.assertFalse(any(p["capabilities"].values()))

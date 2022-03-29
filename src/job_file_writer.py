from pathlib import Path
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class Zone():
    ID:              str = "\"15A\""
    Laser:           str = "LD"
    Power:         float = 15.00
    Skew:          bool  = False 
    Power_Skew:    float = 0.00
    Units:           str = "RAW"
    Dwell:         float = 4228.57
    Track_Spacing: float = 110.00
    Scan:            str = "BI_BT"
    Delay:          bool = False
    ms_Delay:      float = 0.
    Xmin:          float = 10.00
    Xmax:          float = 10.00
    Ymin:          float = -25.00
    Ymax:          float = 25.00
    Repeat:          int = 1

    def write_first_zone(self, f):
        f.write("\n")
        f.write("New_Zone\n")
        for i in self.__dict__:
            f.write(f"    Zone.{i} = {str(self.__dict__[i]).upper()}\n")

    def write_zone(self, prev_zone, f):
        f.write("\n")
        f.write("New_Zone\n")
        for i in self.__dict__:
            if prev_zone.__dict__[i] != self.__dict__[i]:
                f.write(f"    Zone.{i} = {str(self.__dict__[i]).upper()}\n")

@dataclass
class Job():
    naming:  ClassVar[dict[str, str]] = {"CO2_WarmupDelay": "CO2.WarmupDelay", 
                                         "CO2_WarmupWatts": "CO2.WarmupWatts",
                                         "CO2_ChangeDelay": "CO2.ChangeDelay",
                                         "LD_WarmupDelay": "LD.WarmupDelay",
                                         "LD_WarmupWatts": "LD.WarmupWatts",
                                         "LD_ChangeDelay": "LD.ChangeDelay"}
    ID:                str = "\"New Job\""
    RampTime:        float = 125.
    MaxAccel:        float = 5.
    CVDist:          float = 0.50
    Exclude:          bool = True
    WaferDiameter:   float = 100.0
    EdgeExclusion:   float = 3.0
    UseRobustPower:   bool = False
    VelocityPriority: bool = False
    PowerSettleTime: float = 10.0
    MinRetraceVel:   float = 200.0
    MaxRetraceVel:   float = 300.0
    CO2_WarmupDelay: float = 0.0
    CO2_WarmupWatts: float = 50.0
    CO2_ChangeDelay: float = 2.0
    LD_WarmupDelay:  float = 10.0
    LD_WarmupWatts:  float = 1.0
    LD_ChangeDelay:  float = 10.0
    CO2_Origin:        int = -1
    LD_Origin:         int = -1
    LoadWafer:        bool = False
    UnloadWafer:      bool = False
    ManualPowerSet:   bool = False
    OffsetEnable:     bool = False
    Offset_X:        float = 0.000
    Offset_Y:        float = 0.000

    def write_file(self, f):
        for i in self.__dict__:
            if i not in self.naming:
                f.write(f"Job.{i} = {str(self.__dict__[i]).upper()}\n")


def write_zones(zones: list, f):
    zones[0].write_first_zone(f)
    for i in range(1, len(zones)):
        zones[i].write_zone(zones[i-1], f)

if __name__ == "__main__":
   home = Path.home() 
   path = home / "Desktop" / "TR"

   f = open(path / "test.job", "w")
   j = Job()
   j.write_file(f)

   zones = [Zone(ID=f"\"{str(i*4+15)}A\"", Power=i*4+15) for i in range(15)]
   write_zones(zones, f)

   f.close()

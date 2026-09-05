/** 房间类型图标（lucide） */
import { Anchor, DoorOpen, Egg, Flag, Footprints, Gem, HelpCircle, Skull, Swords, Tent, TriangleAlert } from "lucide-react";

export default function RoomIcon({ room, size = 12 }: { room: string; size?: number }) {
  const p = { size, className: "flex-none" };
  switch (room) {
    case "gate":
      return <DoorOpen {...p} />;
    case "corridor":
      return <Footprints {...p} />;
    case "encounter":
      return <Swords {...p} />;
    case "nest":
      return <Egg {...p} />;
    case "rest":
      return <Tent {...p} />;
    case "treasure":
      return <Gem {...p} />;
    case "trap":
      return <TriangleAlert {...p} />;
    case "boss":
      return <Skull {...p} />;
    case "ending":
      return <Flag {...p} />;
    case "unknown":
      return <HelpCircle {...p} />;
    default:
      return <Anchor {...p} />;
  }
}

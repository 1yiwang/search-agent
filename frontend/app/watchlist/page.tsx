import { redirect } from "next/navigation";

export default function WatchlistRedirect() {
  redirect("/library?tab=watching");
}

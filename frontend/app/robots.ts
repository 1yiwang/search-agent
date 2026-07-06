import type { MetadataRoute } from "next";
import { headers } from "next/headers";
import { isDemoHost, isPrivateAppHost } from "@/lib/hosts";

export default async function robots(): Promise<MetadataRoute.Robots> {
  const host = (await headers()).get("host") || "";

  if (isDemoHost(host)) {
    return {
      rules: {
        userAgent: "*",
        allow: ["/demo", "/demo/"],
        disallow: ["/", "/login", "/plan", "/research/"],
      },
    };
  }

  if (isPrivateAppHost(host)) {
    return {
      rules: {
        userAgent: "*",
        disallow: "/",
      },
    };
  }

  return {
    rules: { userAgent: "*", allow: "/" },
  };
}

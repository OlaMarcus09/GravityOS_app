import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Gravity OS",
    short_name: "Gravity OS",
    description: "The operating system for creative careers.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    background_color: "#05060d",
    theme_color: "#05060d",
    orientation: "any",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}

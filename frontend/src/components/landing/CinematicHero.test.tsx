import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CinematicHero, { HERO_POSTER } from "./CinematicHero";

function setReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

beforeEach(() => {
  // jsdom implements no media playback at all: HTMLMediaElement.play is
  // undefined, and the component calls it on mount.
  window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
});

describe("CinematicHero", () => {
  it("plays the film when motion is allowed", async () => {
    setReducedMotion(false);

    render(<CinematicHero />);

    const video = await screen.findByTestId("hero-video");
    expect(video).toHaveAttribute("poster", HERO_POSTER);
    // Autoplay is only permitted for a muted, inline video; without both, a
    // browser silently refuses to start and the hero is a frozen frame.
    expect(video).toHaveAttribute("autoplay");
    expect(video).toHaveProperty("muted", true);
    expect(video).toHaveAttribute("playsinline");
    expect(video).toHaveAttribute("loop");
  });

  it("never mounts the video when the visitor asked for reduced motion", () => {
    setReducedMotion(true);

    render(<CinematicHero />);

    expect(screen.queryByTestId("hero-video")).not.toBeInTheDocument();
  });

  it("drops back to the still frame when the file cannot be played", async () => {
    setReducedMotion(false);

    render(<CinematicHero />);
    fireEvent.error(await screen.findByTestId("hero-video"));

    expect(screen.queryByTestId("hero-video")).not.toBeInTheDocument();
  });

  it("keeps the headline and both calls to action readable without the film", () => {
    setReducedMotion(true);

    render(<CinematicHero />);

    expect(
      screen.getByRole("heading", { level: 1, name: /money leaking out of your ads/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /how it works/i })).toHaveAttribute(
      "href",
      "#how-it-works",
    );
  });

  it("sends the main call to action to a human, not to self-serve sign-up", () => {
    setReducedMotion(true);

    render(<CinematicHero />);

    // Sign-up is not the front door while the first clients are onboarded by
    // hand — and, until the backend is hosted, the form has nothing to post to.
    const cta = screen.getByTestId("hero-cta");
    expect(cta).toHaveTextContent(/free audit/i);
    expect(cta.getAttribute("href")).toMatch(/^(mailto:|https:\/\/wa\.me\/)/);
    expect(screen.queryByRole("link", { name: /create an account/i })).not.toBeInTheDocument();
  });

  it("hides the decorative film from assistive technology", async () => {
    setReducedMotion(false);

    render(<CinematicHero />);

    // The film carries no information the headline does not already state, so
    // it must not be announced. A screen-reader visitor should hear the
    // heading and the links, and nothing else.
    expect(await screen.findByTestId("hero-video")).toHaveAttribute("aria-hidden", "true");
  });
});

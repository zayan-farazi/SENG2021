import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";

type AppLinkProps = {
  href: string;
  className?: string;
  children: ReactNode;
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "children">;

export function navigate(href: string) {
  if (window.location.pathname === href) {
    return;
  }

  window.history.pushState({}, "", href);
  window.dispatchEvent(new Event("app:navigate"));
}

export function AppLink({ href, className, children, onClick, ...rest }: AppLinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);

    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    const target = rest.target;
    if (target && target !== "_self") {
      return;
    }

    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) {
      return;
    }

    event.preventDefault();
    navigate(url.pathname);
  };

  return (
    <a href={href} className={className} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}

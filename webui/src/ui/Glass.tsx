import { Component, type CSSProperties, type ReactNode } from 'react';
import LiquidGlass from 'liquid-glass-react';

/** Liquid Glass 依赖 SVG 滤镜/合成；某些环境会直接抛错，这里兜住并退回普通材质。 */
class GlassBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  constructor(props: { fallback: ReactNode; children: ReactNode }) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    const api = (window as unknown as {
      pywebview?: { api?: { client_error?: (message: string) => void } };
    }).pywebview?.api;
    api?.client_error?.(`LiquidGlass 渲染失败，已回退到普通材质：${String(error)}`);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

interface Props {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  radius?: number;
  padding?: string;
  /** 玻璃越「薄」，下面的内容越清楚；正文区域建议调低 */
  intensity?: 'chrome' | 'surface';
}

/**
 * iOS 的 Liquid Glass 材质。只用在「外壳」类表面上（导航栏、卡片），
 * 不要铺满整屏——这是个逐帧跟着指针重算的滤镜。
 */
export function Glass({
  children, className, style, radius = 16, padding = '0', intensity = 'chrome',
}: Props) {
  const chrome = intensity === 'chrome';

  const fallback = (
    <div
      className={`ios-material ${className ?? ''}`}
      style={{ borderRadius: radius, ...style }}
    >
      {children}
    </div>
  );

  return (
    <GlassBoundary fallback={fallback}>
      <LiquidGlass
        className={className}
        style={{ borderRadius: radius, ...style }}
        cornerRadius={radius}
        padding={padding}
        displacementScale={chrome ? 58 : 34}
        blurAmount={chrome ? 0.12 : 0.06}
        saturation={chrome ? 140 : 120}
        aberrationIntensity={chrome ? 2 : 1}
        elasticity={0.04}
        mode="standard"
      >
        {children}
      </LiquidGlass>
    </GlassBoundary>
  );
}

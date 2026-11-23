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
}

/**
 * iOS 的 Liquid Glass 材质。
 *
 * 这个组件内部对**自己**做了「top/left 50% + translate(-50%,-50%)」的居中定位，
 * 只在「外层容器尺寸 ≈ 自身尺寸」时才互相抵消。所以这里必须套一层同尺寸的
 * `position: relative` 锚点 —— 直接当普通流元素用（比如整宽的顶栏）会被往下/
 * 往右推掉半个父容器，看起来就是「整个控件偏移了」。
 *
 * elasticity 取 0：静态表面不需要跟着鼠标晃，晃起来反而像错位。
 */
export function Glass({ children, className, style, radius = 16, padding = '0' }: Props) {
  const anchorStyle: CSSProperties = { position: 'relative', ...style };

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
      <div style={anchorStyle}>
        <LiquidGlass
          className={className}
          cornerRadius={radius}
          padding={padding}
          displacementScale={52}
          blurAmount={0.1}
          saturation={135}
          aberrationIntensity={2}
          elasticity={0}
          mode="standard"
          style={{ borderRadius: radius, width: '100%' }}
        >
          {children}
        </LiquidGlass>
      </div>
    </GlassBoundary>
  );
}

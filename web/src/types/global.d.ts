// 扩展 Window 接口以包含 Cordova 和 Capacitor 类型
interface Window {
  cordova?: {
    platformId: string;
  };
  Capacitor?: {
    isNative: boolean;
  };
}

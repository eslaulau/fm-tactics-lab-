#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <stdint.h>

static const char kModuleName[] = "@MODULE_NAME@";

static char* append_text(char* out, const char* value) {
    while (*value) *out++ = *value++;
    return out;
}

static char* append_hex(char* out, uintptr_t value) {
    static const char digits[] = "0123456789abcdef";
    char buffer[2 * sizeof(uintptr_t)];
    unsigned count = 0;
    do {
        buffer[count++] = digits[value & 0xf];
        value >>= 4;
    } while (value && count < sizeof(buffer));
    *out++ = '0';
    *out++ = 'x';
    while (count) *out++ = buffer[--count];
    return out;
}

static void platform_probe_fail(const char* api) {
    char event[2048];
    char* cursor = event;
    cursor = append_text(cursor,
        "{\"event\":\"platform_probe_unexpected_call\",\"module\":\"");
    cursor = append_text(cursor, kModuleName);
    cursor = append_text(cursor, "\",\"api\":\"");
    cursor = append_text(cursor, api);
    cursor = append_text(cursor, "\",\"call_stack\":[");

    void* frames[16] = {};
    const USHORT frame_count = CaptureStackBackTrace(1, 16, frames, nullptr);
    const uintptr_t engine = reinterpret_cast<uintptr_t>(
        GetModuleHandleW(L"game_plugin.dll"));
    std::size_t engine_size = 0;
    if (engine) {
        const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(engine);
        if (dos->e_magic == IMAGE_DOS_SIGNATURE && dos->e_lfanew > 0 &&
            dos->e_lfanew < 0x100000) {
            const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(
                engine + static_cast<std::uintptr_t>(dos->e_lfanew));
            if (nt->Signature == IMAGE_NT_SIGNATURE &&
                nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR64_MAGIC)
                engine_size = nt->OptionalHeader.SizeOfImage;
        }
    }
    for (USHORT index = 0; index < frame_count; ++index) {
        if (index) *cursor++ = ',';
        const uintptr_t address = reinterpret_cast<uintptr_t>(frames[index]);
        cursor = append_text(cursor, "{\"address\":\"");
        cursor = append_hex(cursor, address);
        cursor = append_text(cursor, "\"");
        if (engine && address >= engine && address - engine < engine_size) {
            cursor = append_text(cursor, ",\"engine_rva\":\"");
            cursor = append_hex(cursor, address - engine);
            cursor = append_text(cursor, "\"");
        }
        *cursor++ = '}';
    }
    cursor = append_text(cursor, "]}\r\n");
    const DWORD event_size = static_cast<DWORD>(cursor - event);

    OutputDebugStringA(event);
    wchar_t log_path[1024] = {};
    const DWORD length = GetEnvironmentVariableW(
        L"FM27_PLATFORM_STUB_LOG", log_path,
        static_cast<DWORD>(sizeof(log_path) / sizeof(log_path[0])));
    if (length && length < sizeof(log_path) / sizeof(log_path[0])) {
        HANDLE file = CreateFileW(log_path, FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file != INVALID_HANDLE_VALUE) {
            DWORD written = 0;
            WriteFile(file, event, event_size, &written, nullptr);
            CloseHandle(file);
        }
    }

    RaiseFailFastException(nullptr, nullptr, 0);
    TerminateProcess(GetCurrentProcess(), 0xE0420001);
    for (;;) Sleep(INFINITE);
}

#define DEFINE_PLATFORM_PROBE(name) \
    extern "C" __declspec(noreturn) void __cdecl Probe_##name(void) { \
        platform_probe_fail(#name); \
    }

@WRAPPERS@

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) {
    return TRUE;
}

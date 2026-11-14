#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace fm27_platform_boundary {

enum class IatError {
    none,
    invalid_module,
    unreadable_dos_header,
    invalid_dos_header,
    unreadable_nt_headers,
    invalid_nt_headers,
    invalid_import_directory,
    unreadable_import_descriptors,
    invalid_import_descriptor,
    invalid_import_name,
    missing_stub_module,
    duplicate_descriptor,
    invalid_thunk_table,
    iat_target_mismatch,
    import_count_mismatch,
    missing_descriptor_terminator,
    missing_import_descriptor
};

struct IatResult {
    IatError error;
    int target;
    std::size_t index;
    std::size_t expected;
    std::size_t actual;
    std::size_t party_imports;
    std::size_t playfab_imports;

    bool ok() const { return error == IatError::none; }
};

inline const char* error_name(IatError error) {
    switch (error) {
    case IatError::none: return "none";
    case IatError::invalid_module: return "invalid_module";
    case IatError::unreadable_dos_header: return "unreadable_dos_header";
    case IatError::invalid_dos_header: return "invalid_dos_header";
    case IatError::unreadable_nt_headers: return "unreadable_nt_headers";
    case IatError::invalid_nt_headers: return "invalid_nt_headers";
    case IatError::invalid_import_directory: return "invalid_import_directory";
    case IatError::unreadable_import_descriptors: return "unreadable_import_descriptors";
    case IatError::invalid_import_descriptor: return "invalid_import_descriptor";
    case IatError::invalid_import_name: return "invalid_import_name";
    case IatError::missing_stub_module: return "missing_stub_module";
    case IatError::duplicate_descriptor: return "duplicate_descriptor";
    case IatError::invalid_thunk_table: return "invalid_thunk_table";
    case IatError::iat_target_mismatch: return "iat_target_mismatch";
    case IatError::import_count_mismatch: return "import_count_mismatch";
    case IatError::missing_descriptor_terminator: return "missing_descriptor_terminator";
    case IatError::missing_import_descriptor: return "missing_import_descriptor";
    }
    return "unknown";
}

inline IatResult make_result(
    IatError error, int target = -1, std::size_t index = 0,
    std::size_t expected = 0, std::size_t actual = 0,
    std::size_t party = 0, std::size_t playfab = 0) {
    return {error, target, index, expected, actual, party, playfab};
}

inline bool module_range_readable(HMODULE module, const void* address, std::size_t length) {
    if (!module || !address || !length) return false;
    const auto begin = reinterpret_cast<std::uintptr_t>(address);
    if (length > (std::numeric_limits<std::uintptr_t>::max)() - begin) return false;
    const auto end = begin + length;
    auto cursor = begin;

    while (cursor < end) {
        MEMORY_BASIC_INFORMATION memory = {};
        if (!VirtualQuery(reinterpret_cast<const void*>(cursor), &memory, sizeof(memory)))
            return false;
        if (memory.AllocationBase != module || memory.State != MEM_COMMIT ||
            memory.Type != MEM_IMAGE || (memory.Protect & PAGE_GUARD))
            return false;

        const DWORD protection = memory.Protect & 0xff;
        const bool readable = protection == PAGE_READONLY ||
            protection == PAGE_READWRITE || protection == PAGE_WRITECOPY ||
            protection == PAGE_EXECUTE_READ || protection == PAGE_EXECUTE_READWRITE ||
            protection == PAGE_EXECUTE_WRITECOPY;
        if (!readable) return false;

        const auto region_begin = reinterpret_cast<std::uintptr_t>(memory.BaseAddress);
        if (memory.RegionSize > (std::numeric_limits<std::uintptr_t>::max)() - region_begin)
            return false;
        const auto region_end = region_begin + memory.RegionSize;
        if (region_begin > cursor || region_end <= cursor) return false;
        cursor = (std::min)(region_end, end);
    }
    return true;
}

inline bool module_function_address(HMODULE module, const void* address) {
    if (!module || !address) return false;
    MEMORY_BASIC_INFORMATION memory = {};
    if (!VirtualQuery(address, &memory, sizeof(memory))) return false;
    if (memory.AllocationBase != module || memory.State != MEM_COMMIT ||
        memory.Type != MEM_IMAGE || (memory.Protect & PAGE_GUARD))
        return false;
    const DWORD protection = memory.Protect & 0xff;
    return protection == PAGE_EXECUTE || protection == PAGE_EXECUTE_READ ||
        protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY;
}

inline bool image_string(
    HMODULE module, const unsigned char* image, std::size_t image_size,
    std::uint32_t rva, char* output, std::size_t output_size) {
    if (!output || !output_size || rva >= image_size) return false;
    const std::size_t available = (std::min)(image_size - rva, output_size);
    for (std::size_t i = 0; i < available; ++i) {
        if (!module_range_readable(module, image + rva + i, 1)) return false;
        output[i] = static_cast<char>(image[rva + i]);
        if (!output[i]) return true;
    }
    output[output_size - 1] = '\0';
    return false;
}

inline bool ascii_equal_ci(const char* left, const char* right) {
    if (!left || !right) return false;
    while (*left && *right) {
        unsigned char a = static_cast<unsigned char>(*left++);
        unsigned char b = static_cast<unsigned char>(*right++);
        if (a >= 'A' && a <= 'Z') a = static_cast<unsigned char>(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = static_cast<unsigned char>(b - 'A' + 'a');
        if (a != b) return false;
    }
    return *left == 0 && *right == 0;
}

inline IatResult verify_imports(
    HMODULE imported_module, HMODULE party_stub, HMODULE playfab_stub) {
    if (!imported_module || !party_stub || !playfab_stub)
        return make_result(IatError::invalid_module);

    auto image = reinterpret_cast<unsigned char*>(imported_module);
    if (!module_range_readable(imported_module, image, sizeof(IMAGE_DOS_HEADER)))
        return make_result(IatError::unreadable_dos_header);
    auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(image);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        dos->e_lfanew > 0x100000)
        return make_result(IatError::invalid_dos_header);

    const auto nt_offset = static_cast<std::size_t>(dos->e_lfanew);
    if (!module_range_readable(imported_module, image + nt_offset, sizeof(IMAGE_NT_HEADERS64)))
        return make_result(IatError::unreadable_nt_headers);
    auto nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(image + nt_offset);
    const std::size_t required_optional_size =
        offsetof(IMAGE_OPTIONAL_HEADER64, DataDirectory) +
        (IMAGE_DIRECTORY_ENTRY_IMPORT + 1) * sizeof(IMAGE_DATA_DIRECTORY);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
        nt->FileHeader.SizeOfOptionalHeader < required_optional_size ||
        nt->OptionalHeader.NumberOfRvaAndSizes <= IMAGE_DIRECTORY_ENTRY_IMPORT)
        return make_result(IatError::invalid_nt_headers);

    const std::size_t image_size = nt->OptionalHeader.SizeOfImage;
    // Do not probe the entire SizeOfImage range: PE images may contain
    // reserved padding or inaccessible gaps between mapped sections. Every
    // structure and thunk we actually read is checked separately below.
    if (image_size < nt_offset + sizeof(IMAGE_NT_HEADERS64))
        return make_result(IatError::invalid_nt_headers);

    const auto directory =
        nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!directory.VirtualAddress ||
        directory.Size < sizeof(IMAGE_IMPORT_DESCRIPTOR) ||
        directory.VirtualAddress >= image_size ||
        directory.Size > image_size - directory.VirtualAddress)
        return make_result(IatError::invalid_import_directory);
    if (!module_range_readable(
            imported_module, image + directory.VirtualAddress, directory.Size))
        return make_result(IatError::unreadable_import_descriptors);

    const auto descriptors =
        reinterpret_cast<const IMAGE_IMPORT_DESCRIPTOR*>(image + directory.VirtualAddress);
    const std::size_t descriptor_count =
        (std::min)(directory.Size / sizeof(IMAGE_IMPORT_DESCRIPTOR), std::size_t(4096));
    bool seen[2] = {false, false};
    std::size_t observed[2] = {0, 0};
    bool ended = false;

    for (std::size_t d = 0; d < descriptor_count; ++d) {
        const auto& descriptor = descriptors[d];
        const bool zero_descriptor =
            !descriptor.OriginalFirstThunk && !descriptor.TimeDateStamp &&
            !descriptor.ForwarderChain && !descriptor.Name && !descriptor.FirstThunk;
        if (zero_descriptor) {
            ended = true;
            break;
        }
        if (!descriptor.Name)
            return make_result(IatError::invalid_import_descriptor, -1, d, 0, 0,
                               observed[0], observed[1]);

        char imported_name[260] = {};
        if (!image_string(imported_module, image, image_size,
                          descriptor.Name, imported_name, sizeof(imported_name)))
            return make_result(IatError::invalid_import_name, -1, d, 0, 0,
                               observed[0], observed[1]);

        int target = -1;
        if (ascii_equal_ci(imported_name, "PartyWin.dll")) target = 0;
        else if (ascii_equal_ci(imported_name, "PlayFabMultiplayerWin.dll")) target = 1;
        if (target < 0) continue;

        if (seen[target])
            return make_result(IatError::duplicate_descriptor, target, d,
                               target == 0 ? 20 : 19, observed[target],
                               observed[0], observed[1]);
        seen[target] = true;

        HMODULE expected_module = target == 0 ? party_stub : playfab_stub;
        if (!expected_module || !descriptor.FirstThunk)
            return make_result(IatError::missing_stub_module, target, d, 0, 0,
                               observed[0], observed[1]);

        const std::uint32_t lookup_rva =
            descriptor.OriginalFirstThunk ? descriptor.OriginalFirstThunk : descriptor.FirstThunk;
        if (lookup_rva >= image_size || descriptor.FirstThunk >= image_size)
            return make_result(IatError::invalid_thunk_table, target, 0, 0, 0,
                               observed[0], observed[1]);

        const std::size_t max_lookup =
            (image_size - lookup_rva) / sizeof(IMAGE_THUNK_DATA64);
        const std::size_t max_iat =
            (image_size - descriptor.FirstThunk) / sizeof(IMAGE_THUNK_DATA64);
        const std::size_t max_thunks =
            (std::min)((std::min)(max_lookup, max_iat), std::size_t(4096));
        const auto lookup =
            reinterpret_cast<const IMAGE_THUNK_DATA64*>(image + lookup_rva);
        const auto iat =
            reinterpret_cast<const IMAGE_THUNK_DATA64*>(image + descriptor.FirstThunk);

        std::size_t count = 0;
        bool thunk_ended = false;
        for (; count < max_thunks; ++count) {
            const auto lookup_address = lookup + count;
            const auto iat_address = iat + count;
            if (!module_range_readable(imported_module, lookup_address, sizeof(*lookup)) ||
                !module_range_readable(imported_module, iat_address, sizeof(*iat)))
                return make_result(IatError::invalid_thunk_table, target, count, 0, count,
                                   observed[0], observed[1]);
            if (!lookup[count].u1.AddressOfData) {
                thunk_ended = true;
                break;
            }

            const auto function_address = reinterpret_cast<const void*>(
                static_cast<std::uintptr_t>(iat[count].u1.Function));
            if (!module_function_address(expected_module, function_address))
                return make_result(IatError::iat_target_mismatch, target, count,
                                   target == 0 ? 20 : 19, count + 1,
                                   observed[0], observed[1]);
        }
        if (!thunk_ended)
            return make_result(IatError::invalid_thunk_table, target, count, 0, count,
                               observed[0], observed[1]);

        const std::size_t expected_count = target == 0 ? 20 : 19;
        if (count != expected_count)
            return make_result(IatError::import_count_mismatch, target, d,
                               expected_count, count, observed[0], observed[1]);

        observed[target] = count;
    }

    if (!ended)
        return make_result(IatError::missing_descriptor_terminator, -1, descriptor_count,
                           0, descriptor_count, observed[0], observed[1]);
    if (!seen[0] || !seen[1])
        return make_result(IatError::missing_import_descriptor, !seen[0] ? 0 : 1,
                           0, !seen[0] ? 20 : 19, 0, observed[0], observed[1]);

    return make_result(IatError::none, -1, 0, 0, 0, observed[0], observed[1]);
}

} // namespace fm27_platform_boundary

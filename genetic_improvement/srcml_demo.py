#!/usr/bin/env python3
"""
Demo: Converting C/C++ code to XML and back using pylibsrcml
"""

from pylibsrcml import srcMLArchive, srcMLArchiveWriteString, srcMLArchiveRead, srcMLUnit


def to_xml(code: str, language: str) -> str:
    """
    Convert source code to srcML XML format.
    
    Args:
        code: Source code string
        language: Programming language (e.g., "C++", "C", "Java")
    
    Returns:
        XML string representation of the code
    """
    archive = srcMLArchiveWriteString()
    archive.set_language(language)
    archive.enable_solitary_unit()
    
    unit = archive.unit_create()
    unit.parse_memory(code)
    
    archive.write_unit(unit)
    xml_output = archive.close()
    
    return xml_output


def to_code(xml: str, language: str) -> str:
    """
    Convert srcML XML back to source code.
    
    Args:
        xml: srcML XML string
        language: Programming language (e.g., "C++", "C", "Java")
    
    Returns:
        Source code string
    """
    read_archive = srcMLArchiveRead(xml, string_read_mode='source')
    unit = read_archive.read_unit()
    
    if unit:
        code = unit.get_src()
        read_archive.close()
        return code
    else:
        read_archive.close()
        raise ValueError("Failed to parse XML and extract source code")


# Sample C++ code
cpp_code = """#include <iostream>
#include <string>

int main() {
    std::string message = "Hello, World!";
    std::cout << message << std::endl;
    
    for (int i = 0; i < 5; i++) {
        std::cout << "Count: " << i << std::endl;
    }
    
    return 0;
}
"""

print("=" * 60)
print("Original C++ Code:")
print("=" * 60)
print(cpp_code)

# Convert C++ code to XML
print("\n" + "=" * 60)
print("Converting C++ to XML...")
print("=" * 60)

xml_output = to_xml(cpp_code, "C++")
print(xml_output)

# Convert XML back to C++ code
print("\n" + "=" * 60)
print("Converting XML back to C++...")
print("=" * 60)

restored_code = to_code(xml_output, "C++")
print(restored_code)

# Verify round-trip conversion
print("\n" + "=" * 60)
print("Verification:")
print("=" * 60)
if cpp_code.strip() == restored_code.strip():
    print("✓ Round-trip conversion successful - code matches!")
else:
    print("✗ Warning: Restored code differs from original")
    print("\nDifferences:")
    print(f"Original length: {len(cpp_code)}")
    print(f"Restored length: {len(restored_code)}")


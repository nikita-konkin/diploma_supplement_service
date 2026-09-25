package edu.university.xlsxpivot;

import java.util.Locale;

/**
 * File received from the browser in a multipart form.
 */
public final class Upload {

    private final String name;

    private final byte[] content;

    public Upload(final String name, final byte[] content) {
        this.name = name;
        this.content = content;
    }

    public String name() {
        return this.name;
    }

    public byte[] content() {
        return this.content;
    }

    /**
     * Extension to forward to the Python services, which pick the Excel
     * reader by it: ".xls" for old workbooks, ".xlsx" otherwise.
     */
    public String extension() {
        if (this.name.toLowerCase(Locale.ROOT).endsWith(".xls")) {
            return ".xls";
        }
        return ".xlsx";
    }
}

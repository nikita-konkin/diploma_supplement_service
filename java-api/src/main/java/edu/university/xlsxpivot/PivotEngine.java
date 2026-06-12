package edu.university.xlsxpivot;

import java.io.IOException;

/**
 * Produces a pivot workbook from two uploaded workbooks.
 */
@FunctionalInterface
public interface PivotEngine {

    byte[] processPivot(byte[] scores, byte[] disciplines) throws IOException;
}

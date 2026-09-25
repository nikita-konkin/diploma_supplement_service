package edu.university.xlsxpivot;

import java.io.IOException;

/**
 * Produces a pivot workbook from two uploaded workbooks.
 */
@FunctionalInterface
public interface PivotEngine {

    byte[] processPivot(Upload scores, Upload disciplines) throws IOException;
}

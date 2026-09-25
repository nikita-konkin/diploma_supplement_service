package edu.university.xlsxpivot;

/**
 * Upload request that the gateway refuses before calling any service.
 * The message is shown to the user as is.
 */
public final class RejectedRequest extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final int status;

    public RejectedRequest(final int status, final String message) {
        super(message);
        this.status = status;
    }

    public int status() {
        return this.status;
    }
}
